"""Compare segmentation classes in rectangular YOLO regions on a common grid."""

import cv2
import numpy as np

from ALGORITHMS.indicators.oleo_residual_recuperacao import calculate_residual_oil

CLASS_NAMES = ("Water", "Oil", "Gas")


def composition(pixels):
    counts = np.bincount(pixels.ravel(), minlength=4)
    total = int(counts.sum())
    fluid_counts = counts[1:4]
    fluid_total = int(fluid_counts.sum())
    fractions = fluid_counts / fluid_total if fluid_total else [None] * 3
    percentages = [v * 100 if v is not None else None for v in fractions]
    return {
        "area_px": total,
        "fluid_area_px": fluid_total,
        "excluded_wall_px": int(counts[0]),
        "class_pixels": dict(zip(CLASS_NAMES, fluid_counts.tolist())),
        "class_fractions": dict(
            zip(CLASS_NAMES, fractions.tolist() if fluid_total else fractions)
        ),
        "class_percentages": dict(zip(CLASS_NAMES, percentages)),
        "dominant_class": CLASS_NAMES[int(fluid_counts.argmax())]
        if fluid_total
        else None,
        "residual_oil": calculate_residual_oil(
            dict(zip(CLASS_NAMES, fluid_counts.tolist()))
        ),
    }


def analyze_regions(
    mask, detections, size_wh=(1792, 1344), min_confidence=0.70, deadend_class="deadend"
):
    """Use floor/ceil, clipped half-open boxes; aggregate their pixel union."""
    if mask.ndim != 2 or not np.issubdtype(mask.dtype, np.integer):
        raise ValueError("Expected a 2D integer class-ID mask")
    if mask.size == 0 or np.any((mask < 0) | (mask > 3)):
        raise ValueError("Mask must contain only class IDs 0..3")
    width, height = size_wh
    if width <= 0 or height <= 0 or not 0 <= min_confidence <= 1:
        raise ValueError("Invalid analysis dimensions or confidence")
    aligned = cv2.resize(
        mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST
    )
    union = np.zeros(aligned.shape, dtype=bool)
    regions, skipped = [], []
    for index, detection in enumerate(detections, 1):
        # Permit the common dead_end / dead-end spellings as well.
        name = (
            detection["class_name"]
            .lower()
            .replace("_", "")
            .replace("-", "")
            .replace(" ", "")
        )
        expected = (
            deadend_class.lower().replace("_", "").replace("-", "").replace(" ", "")
        )
        if name != expected or detection["confidence"] < min_confidence:
            continue
        box = np.asarray(detection["box_xyxy"], dtype=float)
        if box.shape != (4,) or not np.isfinite(box).all():
            raise ValueError(f"Invalid box at detection {index}")
        if box[2] <= box[0] or box[3] <= box[1]:
            skipped.append(index)
            continue
        x1, y1 = np.floor(box[:2]).astype(int)
        x2, y2 = np.ceil(box[2:]).astype(int)
        x1, x2 = np.clip([x1, x2], 0, width).tolist()
        y1, y2 = np.clip([y1, y2], 0, height).tolist()
        if x2 <= x1 or y2 <= y1:
            skipped.append(index)
            continue
        union[y1:y2, x1:x2] = True
        regions.append(
            {
                "detection_id": index,
                "confidence": detection["confidence"],
                "box_xyxy": box.tolist(),
                "pixel_bounds_xyxy": [x1, y1, x2, y2],
                **composition(aligned[y1:y2, x1:x2]),
            }
        )
    full, inside = composition(aligned), composition(aligned[union])
    report = {
        "analysis_size_wh": [width, height],
        "min_confidence": min_confidence,
        "region_definition": "Union of rectangular detection boxes; not exact anatomical dead-end area",
        "composition_denominator": "Water + Oil + Gas pixels only; walls excluded; fractions sum to 1 when fluid pixels exist, otherwise null",
        "pixel_rule": "floor lower bounds, ceil upper bounds, clip to image; half-open slices",
        "deadend_count": len(regions),
        "skipped_empty_detection_ids": skipped,
        "box_union_image_percent": inside["area_px"] / aligned.size * 100,
        "full_image": full,
        "inside_deadend_boxes": inside,
        "difference_percentage_points": {
            name: inside["class_percentages"][name] - full["class_percentages"][name]
            if inside["fluid_area_px"] and full["fluid_area_px"]
            else None
            for name in CLASS_NAMES
        },
        "regions": regions,
    }
    return report, aligned, union
