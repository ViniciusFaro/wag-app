"""Analyze existing inference outputs without rerunning the models."""

import argparse
import csv
import json
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ALGORITHMS.core.deadend_crops import export_deadend_crops
from ALGORITHMS.core.overlay import CLASS_NAMES, analyze_regions
from ALGORITHMS.indicators.oleo_residual_recuperacao import write_residual_oil_exports

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=ROOT / "ALGORITHMS/data/results/inference_test"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ALGORITHMS/data/results/deadend_analysis"
    )
    parser.add_argument("--min-confidence", type=float, default=0.70)
    parser.add_argument("--deadend-class", default="deadend")
    parser.add_argument(
        "--image",
        type=Path,
        help="Override original image path in the inference report",
    )
    args = parser.parse_args()
    source = json.loads((args.input / "report.json").read_text(encoding="utf-8"))
    mask = cv2.imread(str(args.input / "segmentation_ids.png"), cv2.IMREAD_UNCHANGED)
    if mask is None:
        raise FileNotFoundError(args.input / "segmentation_ids.png")
    report, _aligned, union = analyze_regions(
        mask,
        source["detections"],
        tuple(source["yolo_size_wh"]),
        args.min_confidence,
        args.deadend_class,
    )
    report["source_report"] = str((args.input / "report.json").resolve())
    report["normalization_assumption"] = source.get("normalization_assumption")
    args.output.mkdir(parents=True, exist_ok=True)
    write_residual_oil_exports(report, args.output)
    (args.output / "composition.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    fields = [
        "detection_id",
        "confidence",
        "x1",
        "y1",
        "x2",
        "y2",
        "area_px",
        "fluid_area_px",
        "excluded_wall_px",
        "dominant_class",
    ]
    fields += [
        f"{name}_{suffix}"
        for name in CLASS_NAMES
        for suffix in ["pixels", "fraction", "percent"]
    ]
    with (args.output / "per_deadend.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for region in report["regions"]:
            row = {
                key: region[key]
                for key in [
                    "detection_id",
                    "confidence",
                    "area_px",
                    "fluid_area_px",
                    "excluded_wall_px",
                    "dominant_class",
                ]
            }
            row.update(zip(["x1", "y1", "x2", "y2"], region["pixel_bounds_xyxy"]))
            for name in CLASS_NAMES:
                row[f"{name}_pixels"] = region["class_pixels"][name]
                row[f"{name}_percent"] = region["class_percentages"][name]
                row[f"{name}_fraction"] = region["class_fractions"][name]
            writer.writerow(row)
    if not cv2.imwrite(
        str(args.output / "deadend_box_union.png"), union.astype(np.uint8) * 255
    ):
        raise OSError("Could not write union mask")
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    for shift, key, label, color in [
        (-0.2, "full_image", "Full image", "#526580"),
        (0.2, "inside_deadend_boxes", "Inside dead-end boxes (union)", "#bc602a"),
    ]:
        values = [
            report[key]["class_fractions"][name]
            if report[key]["class_fractions"][name] is not None
            else np.nan
            for name in CLASS_NAMES
        ]
        bars = ax.bar(x + shift, values, width=0.4, label=label, color=color)
        ax.bar_label(bars, fmt="%.4f", fontsize=9, padding=3)
    ax.set(
        xticks=x,
        xticklabels=CLASS_NAMES,
        ylabel="Fraction of fluid pixels (wall excluded)",
        ylim=(0, 1),
        title=f"Fluid composition | {report['deadend_count']} boxes | water + oil + gas = 1",
    )
    ax.legend()
    if not report["inside_deadend_boxes"]["fluid_area_px"]:
        ax.text(
            0.5,
            0.5,
            "No fluid pixels inside matching boxes; composition unavailable",
            transform=ax.transAxes,
            ha="center",
        )
    fig.savefig(args.output / "composition_comparison.png", dpi=160)
    plt.close(fig)
    print(
        f"Analyzed {report['deadend_count']} boxes; union covers {report['box_union_image_percent']:.2f}% of the image"
    )
    for name in CLASS_NAMES:
        print(
            f"{name}: full {report['full_image']['class_fractions'][name]}; inside {report['inside_deadend_boxes']['class_fractions'][name]}"
        )
    print(f"Outputs: {args.output}")
    image_path = args.image or Path(source["image"])
    original_bgr = cv2.imread(str(image_path))
    if original_bgr is None:
        raise FileNotFoundError(
            f"Cannot read original image for crops: {image_path}; use --image to override"
        )
    manifest = export_deadend_crops(
        cv2.cvtColor(original_bgr, cv2.COLOR_BGR2RGB),
        _aligned,
        report,
        args.output / "deadends",
    )
    print(f"Exported {manifest['count']} individual dead-end crops and manifest.json")


if __name__ == "__main__":
    main()
