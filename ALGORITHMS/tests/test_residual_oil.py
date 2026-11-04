import csv
import io
import json

import numpy as np
import pytest

from ALGORITHMS.core.overlay import analyze_regions
from ALGORITHMS.indicators.oleo_residual_recuperacao import (
    calculate_residual_oil,
    write_residual_oil_exports,
)


def test_oil_and_gas_are_residual_and_wall_is_excluded():
    result = calculate_residual_oil({"Water": 30, "Oil": 50, "Gas": 20, "Wall": 900})
    assert result["initial_oil_equivalent_px"] == 100
    assert result["initial_oil_equivalent_percent"] == 100
    assert result["residual_oil_gas_px"] == 70
    assert result["residual_percent"] == 70
    assert result["removed_oil_equivalent_px"] == 30
    assert result["removed_percent"] == 30
    assert result["oil_percent"] == 50
    assert result["gas_percent"] == 20


@pytest.mark.parametrize(
    "counts, remaining, removed",
    [
        ({"Water": 10, "Oil": 0, "Gas": 0}, 0, 100),
        ({"Water": 0, "Oil": 10, "Gas": 0}, 100, 0),
        ({"Water": 0, "Oil": 0, "Gas": 10}, 100, 0),
        ({"Water": 1, "Oil": 1, "Gas": 1}, 200 / 3, 100 / 3),
    ],
)
def test_residual_and_removed_balance(counts, remaining, removed):
    result = calculate_residual_oil(counts)
    assert result["residual_percent"] == pytest.approx(remaining)
    assert result["removed_percent"] == pytest.approx(removed)
    assert result["residual_percent"] + result["removed_percent"] == pytest.approx(100)
    assert (
        result["residual_oil_gas_px"] + result["removed_oil_equivalent_px"]
        == result["initial_oil_equivalent_px"]
    )


def test_empty_fluid_area_has_undefined_percentages():
    result = calculate_residual_oil(dict(Water=0, Oil=0, Gas=0, Wall=100))
    assert result["initial_oil_equivalent_px"] == 0
    assert all(
        value is None for key, value in result.items() if key.endswith("_percent")
    )
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("invalid", [-1, 1.5, True])
def test_reject_invalid_pixel_counts(invalid):
    with pytest.raises(ValueError):
        calculate_residual_oil(dict(Water=invalid, Oil=2, Gas=0))


def test_overlapping_boxes_use_union_counts_and_exports(tmp_path):
    mask = np.array([[1, 2, 2, 3, 0, 1]] * 2, dtype=np.uint8)
    detections = [
        dict(box_xyxy=box, confidence=0.9, class_name="deadend")
        for box in ([0, 0, 4, 2], [2, 0, 6, 2])
    ]
    analysis, _, _ = analyze_regions(mask, detections, size_wh=(6, 2))
    union = analysis["inside_deadend_boxes"]["residual_oil"]
    assert union["initial_oil_equivalent_px"] == 10
    assert union["residual_percent"] == 60
    assert union["removed_percent"] == 40
    assert analysis["regions"][0]["residual_oil"]["residual_percent"] == 75
    report = write_residual_oil_exports(analysis, tmp_path)
    assert json.loads((tmp_path / "residual_oil.json").read_text()) == report
    rows = list(
        csv.DictReader(io.StringIO((tmp_path / "residual_oil.csv").read_text()))
    )
    assert len(rows) == 4
    assert rows[1]["scope"] == "deadends_union"
    assert float(rows[1]["removed_percent"]) == 40
