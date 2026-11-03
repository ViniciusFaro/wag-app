"""Inference dimensions, colors and tiled YOLOv5 pipeline from the specification."""

import os
import pathlib
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import torch
from torchvision.ops import batched_nms

from .dcaunet import DCAUNet

ROOT = Path(__file__).resolve().parents[2]
COLORS = np.array(
    [[255, 255, 0], [0, 0, 255], [255, 0, 0], [0, 255, 0]], dtype=np.uint8
)
CLASS_NAMES = ["Wall", "Water", "Oil", "Gas"]


def generate_positions(length, tile_size=224, stride=168):
    if length <= tile_size:
        return [0]
    positions = list(range(0, length - tile_size + 1, stride))
    if positions[-1] != length - tile_size:
        positions.append(length - tile_size)
    return positions


@torch.inference_mode()
def segment(image, weights, device):
    model = DCAUNet()
    model.load_state_dict(
        torch.load(weights, map_location="cpu", weights_only=True), strict=True
    )
    model.to(device).eval()
    # Specification gives CHW = 3,768,576. RGB /255 is an explicit assumption.
    resized = cv2.resize(image, (576, 768), interpolation=cv2.INTER_LINEAR)
    tensor = (
        torch.from_numpy(resized.copy())
        .permute(2, 0, 1)
        .float()
        .div(255)
        .unsqueeze(0)
        .to(device)
    )
    logits = model(tensor)
    if logits.shape != (1, 4, 768, 576) or not torch.isfinite(logits).all():
        raise RuntimeError(f"Invalid segmentation logits: {logits.shape}")
    return logits.argmax(1)[0].cpu().numpy().astype(np.uint8)


def load_yolo(weights, device):
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".uv-cache" / "ultralytics"))
    torch.hub.set_dir(str(ROOT / ".uv-cache" / "torch" / "hub"))
    # Legacy YOLOv5 checkpoints contain a serialized model, not a state_dict.
    # Restrict full deserialization to this explicitly supplied, trusted weight file.
    original_load = torch.load

    def load_checkpoint(path, *args, **kwargs):
        if (
            isinstance(path, (str, Path))
            and Path(path).resolve() == Path(weights).resolve()
        ):
            kwargs["weights_only"] = False
            if os.name == "nt":
                # Colab checkpoints may include Linux paths in training metadata.
                with patch("pathlib.PosixPath", pathlib.WindowsPath):
                    return original_load(path, *args, **kwargs)
        return original_load(path, *args, **kwargs)

    os.environ.setdefault("YOLOv5_AUTOINSTALL", "false")
    with patch("torch.load", side_effect=load_checkpoint):
        model = torch.hub.load(
            "ultralytics/yolov5:v7.0", "custom", path=str(weights), trust_repo=True
        )
    model.to(device).eval()
    model.conf, model.iou = 0.25, 0.45
    return model


@torch.inference_mode()
def detect(image, model):
    image = cv2.resize(image, (1792, 1344), interpolation=cv2.INTER_LINEAR)
    detections = []
    tiles = [(x, y) for y in generate_positions(1344) for x in generate_positions(1792)]
    for index, (x, y) in enumerate(tiles):
        rows = (
            model(image[y : y + 224, x : x + 224], size=224)
            .xyxy[0]
            .detach()
            .cpu()
            .clone()
        )
        if len(rows):
            rows[:, [0, 2]] += x
            rows[:, [1, 3]] += y
            detections.append(rows)
        if (index + 1) % 20 == 0:
            print(f"YOLO tiles: {index + 1}/{len(tiles)}", flush=True)
    rows = torch.cat(detections) if detections else torch.empty((0, 6))
    keep = batched_nms(rows[:, :4], rows[:, 4], rows[:, 5].long(), 0.45)
    rows = rows[keep]
    return image, rows[rows[:, 4] >= 0.70], len(tiles)
