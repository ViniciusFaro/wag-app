import copy
import csv
import io

import pytest
from fastapi.testclient import TestClient

from API.FASTAPI.app import main

client = TestClient(main.app)


@pytest.fixture
def legacy_analysis(monkeypatch):
    """Saved pre-feature records have counts but no residual_oil fields."""
    region = {
        "detection_id": 1,
        "id": "deadend_0001",
        "class_pixels": dict(Water=0, Oil=2, Gas=0),
        "assets": {},
    }
    files = {
        "composition.json": {
            "analysis_size_wh": [1792, 1344],
            "deadend_count": 1,
            "box_union_image_percent": 5,
            "full_image": {"class_pixels": dict(Water=30, Oil=50, Gas=20)},
            "inside_deadend_boxes": {"class_pixels": dict(Water=0, Oil=2, Gas=0)},
        },
        "report.json": {
            "original_size_wh": [1792, 1344],
            "total_seconds": 1,
            "device": "cpu",
        },
        "manifest.json": {"items": [region]},
    }
    monkeypatch.setattr(main, "read_json", lambda path: copy.deepcopy(files[path.name]))
    return files


def test_legacy_saved_counts_are_enriched_without_inference(legacy_analysis):
    result = client.get("/api/analyses/sample").json()
    assert result["composition"]["full_image"]["residual_oil"]["removed_percent"] == 30
    assert result["deadends"][0]["residual_oil"]["residual_percent"] == 100
    assert "residual_oil" not in legacy_analysis["composition.json"]["full_image"]
    exported = client.get(result["assets"]["residual_report"])
    assert exported.status_code == 200
    assert exported.json()["deadends"]["initial_oil_equivalent_px"] == 2
    assert exported.json()["full_image"]["residual_percent"] == 70
    csv_response = client.get(result["assets"]["residual_csv"])
    rows = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert len(rows) == 3
    assert rows[1]["removed_percent"] == "0.0"
    assert "attachment" in csv_response.headers["content-disposition"]


def test_unknown_or_pending_analysis_cannot_be_exported(monkeypatch):
    assert client.get("/api/analyses/invalid/residual-oil").status_code == 404
    monkeypatch.setattr(main, "job", lambda job_id: {"status": "queued"})
    assert client.get("/api/analyses/test/residual-oil").status_code == 409
