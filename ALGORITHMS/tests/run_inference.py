"""Real-weight integration test: python -m ALGORITHMS.tests.run_inference."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from ALGORITHMS.core.inference import (
    CLASS_NAMES,
    COLORS,
    ROOT,
    detect,
    load_yolo,
    segment,
)


def save_rgb(path, image):
    if not cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR)):
        raise OSError(f"Could not save {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", type=Path, default=ROOT / "ALGORITHMS/data/raw/train.png"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ALGORITHMS/data/results/inference_test"
    )
    parser.add_argument(
        "--unet",
        type=Path,
        default=ROOT / "MODELS/unet/dcaunet_ema_combined_loss_weighted.pt",
    )
    parser.add_argument("--yolo", type=Path, default=ROOT / "MODELS/yolo/best.pt")
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    args = parser.parse_args()
    for path in [args.image, args.unet, args.yolo]:
        if not path.is_file():
            raise FileNotFoundError(path)
    args.output.mkdir(parents=True, exist_ok=True)
    bgr = cv2.imread(str(args.image))
    if bgr is None:
        raise ValueError(f"Cannot decode {args.image}")
    image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    torch.set_num_threads(min(8, torch.get_num_threads()))
    start = time.perf_counter()
    print(f"Running U-Net on {args.device}...", flush=True)
    mask = segment(image, args.unet, args.device)
    cv2.imwrite(str(args.output / "segmentation_ids.png"), mask)
    save_rgb(args.output / "segmentation.png", COLORS[mask])
    unet_seconds = time.perf_counter() - start
    print(f"U-Net passed in {unet_seconds:.1f}s. Loading YOLOv5...", flush=True)
    model = load_yolo(args.yolo, args.device)
    canvas, rows, tiles = detect(image, model)
    aligned = cv2.resize(mask, (1792, 1344), interpolation=cv2.INTER_NEAREST)
    save_rgb(args.output / "segmentation_aligned.png", COLORS[aligned])
    overlay = (canvas.astype(np.float32) * 0.5 + COLORS[aligned] * 0.5).astype(np.uint8)
    detections = []
    for row in rows.tolist():
        x1, y1, x2, y2, confidence, cls = row
        if not (0 <= x1 <= x2 <= 1792 and 0 <= y1 <= y2 <= 1344):
            raise AssertionError(f"Out-of-bounds box: {row}")
        name = model.names[int(cls)]
        detections.append(
            {
                "box_xyxy": row[:4],
                "confidence": confidence,
                "class_id": int(cls),
                "class_name": name,
            }
        )
        for target in [canvas, overlay]:
            cv2.rectangle(
                target, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2
            )
            cv2.putText(
                target,
                f"{name} {confidence:.2f}",
                (int(x1), max(15, int(y1) - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                1,
            )
    save_rgb(args.output / "detections.png", canvas)
    save_rgb(args.output / "overlay.png", overlay)
    report = {
        "image": str(args.image),
        "original_size_wh": [image.shape[1], image.shape[0]],
        "device": args.device,
        "unet_input_chw": [3, 768, 576],
        "normalization_assumption": "RGB float32 /255; confirm against training",
        "yolo_size_wh": [1792, 1344],
        "tile_size": 224,
        "overlap": 0.25,
        "tiles": tiles,
        "confidence": 0.25,
        "display_confidence": 0.70,
        "nms_iou": 0.45,
        "class_colors_rgb": dict(zip(CLASS_NAMES, COLORS.tolist())),
        "class_percentages": dict(
            zip(
                CLASS_NAMES,
                (np.bincount(mask.ravel(), minlength=4) / mask.size * 100).tolist(),
            )
        ),
        "detections": detections,
        "unet_seconds": unet_seconds,
        "total_seconds": time.perf_counter() - start,
    }
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        f"PASS: both models; {len(rows)} displayed detections; outputs: {args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
