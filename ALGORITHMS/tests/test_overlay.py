import numpy as np
import pytest

from ALGORITHMS.core.overlay import analyze_regions


def detection(box, name="deadend", confidence=0.9):
    return {"box_xyxy": box, "class_name": name, "confidence": confidence}


def test_known_composition_and_overlapping_union():
    mask = np.array([[0, 1, 2, 3], [0, 1, 2, 3]], dtype=np.uint8)
    report, _, union = analyze_regions(
        mask, [detection([0, 0, 3, 2]), detection([2, 0, 4, 2])], (4, 2)
    )
    assert report["full_image"]["class_percentages"] == pytest.approx(
        dict.fromkeys(["Water", "Oil", "Gas"], 100 / 3)
    )
    assert report["regions"][0]["class_pixels"] == {
        "Water": 2,
        "Oil": 2,
        "Gas": 0,
    }
    assert report["inside_deadend_boxes"]["area_px"] == 8
    assert sum(r["area_px"] for r in report["regions"]) == 10
    assert union.all()
    assert sum(report["full_image"]["class_fractions"].values()) == pytest.approx(1)
    assert report["regions"][0]["class_fractions"] == {
        "Water": 0.5,
        "Oil": 0.5,
        "Gas": 0.0,
    }


def test_scaling_clipping_fractional_boxes_and_filtering():
    mask = np.array([[0, 1], [2, 3]], dtype=np.uint8)
    report, aligned, _ = analyze_regions(
        mask,
        [
            detection([-1, -2, 1.2, 1.2]),
            detection([0, 0, 4, 4], "throat"),
            detection([0, 0, 4, 4], confidence=0.6),
            detection([8, 8, 9, 9]),
        ],
        (4, 4),
    )
    assert aligned.shape == (4, 4)
    assert report["deadend_count"] == 1
    assert report["regions"][0]["excluded_wall_px"] == 4
    assert report["regions"][0]["fluid_area_px"] == 0
    assert all(
        value is None for value in report["regions"][0]["class_fractions"].values()
    )
    assert report["box_union_image_percent"] == 25
    assert report["skipped_empty_detection_ids"] == [4]


def test_no_detections_has_no_dominant_class_or_difference():
    report, _, _ = analyze_regions(np.zeros((2, 2), dtype=np.uint8), [], (2, 2))
    assert report["inside_deadend_boxes"]["dominant_class"] is None
    assert report["box_union_image_percent"] == 0
    assert all(v is None for v in report["difference_percentage_points"].values())


def test_rejects_colored_masks():
    with pytest.raises(ValueError):
        analyze_regions(np.zeros((2, 2, 3), dtype=np.uint8), [])
