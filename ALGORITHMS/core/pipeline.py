"""Reusable image-to-analysis pipeline for the web API."""

import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from .deadend_crops import export_deadend_crops
from .inference import COLORS, ROOT, detect, load_yolo, segment
from .overlay import CLASS_NAMES, analyze_regions
from ALGORITHMS.indicators.oleo_residual_recuperacao import write_residual_oil_exports


def run_analysis(image_path, output_dir, progress=lambda stage: None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    bgr = cv2.imread(str(image_path))
    if bgr is None:
        raise ValueError("Could not read the uploaded image")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_num_threads(min(8, torch.get_num_threads()))

    def save(name, image, colored=True):
        data = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if colored else image
        if not cv2.imwrite(str(output_dir / name), data):
            raise OSError(f"Could not write {name}")

    progress("segmentation")
    mask = segment(
        rgb, ROOT / "MODELS/unet/dcaunet_ema_combined_loss_weighted.pt", device
    )
    save("segmentation_ids.png", mask, colored=False)
    progress("detection")
    model = load_yolo(ROOT / "MODELS/yolo/best.pt", device)
    canvas, rows, tiles = detect(rgb, model)
    aligned = cv2.resize(mask, (1792, 1344), interpolation=cv2.INTER_NEAREST)
    save("original.png", rgb)
    save("segmentation.png", COLORS[aligned])
    overlay = cv2.addWeighted(canvas, 0.5, COLORS[aligned], 0.5, 0)
    detections = []
    for x1, y1, x2, y2, confidence, cls in rows.tolist():
        detections.append(
            {
                "box_xyxy": [x1, y1, x2, y2],
                "confidence": confidence,
                "class_id": int(cls),
                "class_name": model.names[int(cls)],
            }
        )
        for target in (canvas, overlay):
            cv2.rectangle(
                target, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2
            )
    save("detections.png", canvas)
    save("overlay.png", overlay)
    progress("composition")
    analysis, aligned, union = analyze_regions(mask, detections)
    write_residual_oil_exports(analysis, output_dir)
    save("deadend_box_union.png", union.astype(np.uint8) * 255, colored=False)
    export_deadend_crops(rgb, aligned, analysis, output_dir / "deadends")
    analysis["normalization_assumption"] = "RGB float32 /255; confirm against training"
    (output_dir / "composition.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )
    with (output_dir / "per_deadend.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        fields = ["id", "confidence", "fluid_area_px", "excluded_wall_px"] + [
            f"{name}_fraction" for name in CLASS_NAMES
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for region in analysis["regions"]:
            writer.writerow(
                dict(
                    id=region["detection_id"],
                    confidence=region["confidence"],
                    fluid_area_px=region["fluid_area_px"],
                    excluded_wall_px=region["excluded_wall_px"],
                    **{
                        f"{name}_fraction": region["class_fractions"][name]
                        for name in CLASS_NAMES
                    },
                )
            )
    report = {
        "image": str(image_path),
        "original_size_wh": [rgb.shape[1], rgb.shape[0]],
        "yolo_size_wh": [1792, 1344],
        "device": device,
        "tiles": tiles,
        "detections": detections,
        "total_seconds": time.perf_counter() - start,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
