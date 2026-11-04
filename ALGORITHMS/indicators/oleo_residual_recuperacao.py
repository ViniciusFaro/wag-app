"""Area-based residual-oil estimate under an initially oil-filled fluid-area assumption."""

import csv
import io
import json
from numbers import Integral
from pathlib import Path

RESIDUAL_FIELDS = (
    "water_px",
    "oil_px",
    "gas_px",
    "initial_oil_equivalent_px",
    "residual_oil_gas_px",
    "removed_oil_equivalent_px",
    "initial_oil_equivalent_percent",
    "oil_percent",
    "gas_percent",
    "residual_percent",
    "removed_percent",
)


def calculate_residual_oil(class_pixels):
    """Ignore walls; count oil + gas as residual and water as displaced oil.

    Counts are areas in pixels, not volumes. Zero fluid area has undefined
    percentages (None), even when a rectangular region contains wall pixels.
    """
    counts = {}
    for name in ("Water", "Oil", "Gas"):
        value = class_pixels[name]
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer pixel count")
        counts[name] = int(value)
    water, oil, gas = (counts[name] for name in ("Water", "Oil", "Gas"))
    initial = water + oil + gas
    residual = oil + gas

    def percentage(area):
        return area / initial * 100 if initial else None

    return {
        "water_px": water,
        "oil_px": oil,
        "gas_px": gas,
        "initial_oil_equivalent_px": initial,
        "residual_oil_gas_px": residual,
        "removed_oil_equivalent_px": initial - residual,
        "initial_oil_equivalent_percent": 100.0 if initial else None,
        "oil_percent": percentage(oil),
        "gas_percent": percentage(gas),
        "residual_percent": percentage(residual),
        "removed_percent": percentage(water),
    }


def with_residual_oil(composition):
    """Enrich both newly computed and legacy saved class-count records."""
    return {
        **composition,
        "residual_oil": calculate_residual_oil(composition["class_pixels"]),
    }


def residual_oil_report(full_image, deadends, regions):
    return {
        "method": {
            "initial_oil_equivalent": "Water + Oil + Gas",
            "residual": "Oil + Gas",
            "removed": "Water",
            "percentage_denominator": "Water + Oil + Gas",
            "units": "pixel area",
            "wall_excluded": True,
            "assumption": "The current fluid area is assumed initially filled with oil; this is an area-equivalent estimate from one image, not a time-series measurement.",
            "aggregate": "Union of detected boxes; overlapping pixels counted once, not a mean of per-region percentages.",
        },
        "full_image": calculate_residual_oil(full_image["class_pixels"]),
        "deadends": calculate_residual_oil(deadends["class_pixels"]),
        "regions": [
            {
                "detection_id": region["detection_id"],
                **calculate_residual_oil(region["class_pixels"]),
            }
            for region in regions
        ],
    }


def residual_oil_csv(report):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=["scope", "detection_id", *RESIDUAL_FIELDS]
    )
    writer.writeheader()
    writer.writerow({"scope": "full_image", **report["full_image"]})
    writer.writerow({"scope": "deadends_union", **report["deadends"]})
    for region in report["regions"]:
        writer.writerow({"scope": "deadend", **region})
    return stream.getvalue()


def write_residual_oil_exports(analysis, output_dir):
    report = residual_oil_report(
        analysis["full_image"], analysis["inside_deadend_boxes"], analysis["regions"]
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "residual_oil.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "residual_oil.csv").write_text(
        residual_oil_csv(report), encoding="utf-8", newline=""
    )
    return report
