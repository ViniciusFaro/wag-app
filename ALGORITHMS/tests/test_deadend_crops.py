import json

import cv2
import numpy as np
import pytest

from ALGORITHMS.core.deadend_crops import COLORS, export_deadend_crops
from ALGORITHMS.core.overlay import analyze_regions


def test_crops_match_pixels_and_manifest(tmp_path):
    image = np.arange(4 * 4 * 3, dtype=np.uint8).reshape(4, 4, 3)
    mask = np.tile(np.arange(4, dtype=np.uint8), (4, 1))
    analysis, aligned, _ = analyze_regions(
        mask,
        [{"box_xyxy": [1, 1, 4, 3], "confidence": 0.9, "class_name": "deadend"}],
        (4, 4),
    )
    manifest = export_deadend_crops(image, aligned, analysis, tmp_path)
    item = manifest["items"][0]
    assert item["size_wh"] == [3, 2]
    assert sum(item["class_fractions"].values()) == pytest.approx(1)
    saved = cv2.cvtColor(
        cv2.imread(str(tmp_path / item["assets"]["original"])), cv2.COLOR_BGR2RGB
    )
    np.testing.assert_array_equal(saved, image[1:3, 1:4])
    ids = cv2.imread(str(tmp_path / item["assets"]["class_ids"]), cv2.IMREAD_UNCHANGED)
    np.testing.assert_array_equal(ids, mask[1:3, 1:4])
    colored = cv2.cvtColor(
        cv2.imread(str(tmp_path / item["assets"]["segmentation"])), cv2.COLOR_BGR2RGB
    )
    np.testing.assert_array_equal(colored, COLORS[ids])
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest
    assert all((tmp_path / path).is_file() for path in item["assets"].values())


def test_empty_export_and_invalid_alignment(tmp_path):
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    analysis, aligned, _ = analyze_regions(np.zeros((4, 4), dtype=np.uint8), [], (4, 4))
    manifest = export_deadend_crops(image, aligned, analysis, tmp_path)
    assert manifest["count"] == 0
    assert manifest["items"] == []
    assert "preview" not in manifest
    with pytest.raises(ValueError):
        export_deadend_crops(image, aligned[:2], analysis, tmp_path)
