"""Exercise real SQL transactions and HTTP contracts without running ML models."""

import copy
import csv
import io
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from ALGORITHMS.core.overlay import analyze_regions
from API.FASTAPI.app import main
from API.FASTAPI.app.api.v1.endpoints import endpoints as experiments
from API.FASTAPI.app.db import session as database
from API.FASTAPI.app.db.base import Base
from API.FASTAPI.app.db.models import Experiment, RegionResult

ORIGINAL_ANALYSIS_LOADER = experiments.get_completed_analysis


def analysis_result(mask=None, boxes=None, analysis_id="a" * 32):
    if mask is None:
        mask = np.array(
            [[0, 1, 2, 3, 1, 2], [2, 2, 3, 1, 0, 1], [1, 2, 2, 3, 1, 0]], dtype=np.uint8
        )
    if boxes is None:
        boxes = [[0, 0, 3, 2], [2, 0, 4, 2]]
    height, width = mask.shape
    analysis, _, _ = analyze_regions(
        mask,
        [
            {"class_name": "deadend", "confidence": 0.9, "box_xyxy": box}
            for box in boxes
        ],
        (width, height),
    )
    regions = [
        {
            **region,
            "id": f"deadend_{region['detection_id']:04d}",
            "assets": {"class_ids": "/api/files/example/class_ids.png"},
        }
        for region in analysis["regions"]
    ]
    return {
        "id": analysis_id,
        "status": "completed",
        "filename": "micromodelo_área.png",
        "is_sample": False,
        "created_at": "2026-11-04T10:00:00-03:00",
        "completed_at": "2026-11-04T13:00:02Z",
        "image_sha256": "b" * 64,
        "image_size_wh": [60, 30],
        "analysis_size_wh": [width, height],
        "segmentation_size_wh": [3, 2],
        "inference_seconds": 2.5,
        "device": "cpu",
        "deadend_count": len(regions),
        "coverage_percent": analysis["box_union_image_percent"],
        "parameters": {
            "min_confidence": 0.7,
            "region_definition": analysis["region_definition"],
        },
        "inference": {
            "tiles": 4,
            "model_weights": {"UNet": "unet.pt", "YOLO": "yolo.pt"},
        },
        "composition": {
            "full_image": analysis["full_image"],
            "deadends": analysis["inside_deadend_boxes"],
        },
        "assets": {"original": "/api/files/example/original.png"},
        "deadends": regions,
    }


@pytest.fixture
def stored_api(tmp_path, monkeypatch):
    engine = database.make_engine(
        f"sqlite:///{(tmp_path / 'experiments.db').as_posix()}"
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    monkeypatch.setattr(main, "JOBS", jobs)
    with TestClient(main.app) as client:
        yield client, factory, engine
    engine.dispose()


@pytest.fixture
def source(monkeypatch):
    result = analysis_result()
    monkeypatch.setattr(
        experiments, "get_completed_analysis", lambda _id: copy.deepcopy(result)
    )
    return result


def save(client, result, **fields):
    return client.post("/api/experiments", json={"analysis_id": result["id"], **fields})


def test_save_get_and_sql_metrics(stored_api, source):
    client, factory, _ = stored_api
    response = save(client, source, name="Ensaio WAG", notes="Amostra 01")
    assert response.status_code == 201, response.text
    result = response.json()
    assert response.headers["location"].endswith(result["id"])
    assert result["filename"] == source["filename"]
    assert result["created_at"] == "2026-11-04T13:00:00Z"
    assert result["image_size_wh"] == [60, 30]
    assert result["analysis_size_wh"] == [6, 3]
    assert result["segmentation_size_wh"] == [3, 2]
    assert result["notes"] == "Amostra 01"
    assert result["inference"] == source["inference"]
    assert result["image_sha256"] == "b" * 64
    assert len(result["deadends"]) == result["deadend_count"] == 2
    groups = result["composition"]
    for name in ("Water", "Oil", "Gas"):
        assert (
            groups["full_image"]["class_pixels"][name]
            == groups["deadends"]["class_pixels"][name]
            + groups["outside_deadends"]["class_pixels"][name]
        )
    assert (
        groups["deadends"]["area_px"] == 8
    )  # Two overlapping rectangles have area 10 in total.
    assert groups["outside_deadends"]["area_px"] == 10
    assert groups["outside_deadends"]["residual_oil"]["residual_percent"] == 50
    assert groups["outside_deadends"]["class_fractions"]["Oil"] == 3 / 8
    assert client.get(f"/api/experiments/{result['id']}").json() == result
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(RegionResult)) == 5
        outside = db.scalar(
            select(RegionResult).where(RegionResult.scope == "outside_deadends")
        )
        assert outside.oil_px == 3
        assert outside.residual_fraction == 0.5
        assert outside.excluded_wall_px == 2


def test_repeated_save_is_idempotent_even_without_source_files(
    stored_api, source, monkeypatch
):
    client, factory, _ = stored_api
    first = save(client, source, name="Ensaio original").json()

    def missing_source(_id):
        raise AssertionError("Saved experiments must not need analysis files")

    monkeypatch.setattr(experiments, "get_completed_analysis", missing_source)
    response = save(client, source, name="Nome diferente")
    assert response.status_code == 200
    assert response.json() == first
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Experiment)) == 1


def test_list_pagination_and_filters(stored_api, source):
    client, _, _ = stored_api
    first = save(client, source).json()
    source.update(id="c" * 32, filename="teste%literal.png")
    second = save(client, source).json()
    page = client.get("/api/experiments?limit=1").json()
    assert page["total"] == 2
    assert page["items"][0]["id"] == second["id"]
    assert "deadends" not in page["items"][0]  # Regions are loaded only in the detail.
    assert (
        client.get("/api/experiments?limit=1&offset=1").json()["items"][0]["id"]
        == first["id"]
    )
    assert client.get("/api/experiments", params={"filename": "%"}).json()["total"] == 1
    assert (
        client.get(
            "/api/experiments", params={"analysis_id": first["analysis_id"]}
        ).json()["total"]
        == 1
    )
    assert (
        client.get(
            "/api/experiments",
            params={
                "saved_from": second["saved_at"],
                "saved_until": second["saved_at"],
            },
        ).json()["total"]
        == 1
    )
    for params in (
        {"limit": 101},
        {"offset": -1},
        {"saved_from": "2030-01-01", "saved_until": "2000-01-01"},
    ):
        assert client.get("/api/experiments", params=params).status_code == 422


def test_delete_cascades_and_preserves_files(stored_api, source, tmp_path):
    client, factory, _ = stored_api
    artifact = tmp_path / "mask.png"
    artifact.write_bytes(b"retained artifact")
    result = save(client, source).json()
    assert client.delete(f"/api/experiments/{result['id']}").status_code == 204
    assert client.get(f"/api/experiments/{result['id']}").status_code == 404
    assert client.delete(f"/api/experiments/{result['id']}").status_code == 404
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(RegionResult)) == 0
    assert artifact.read_bytes() == b"retained artifact"


def test_results_survive_reconnect_and_unavailable_outputs(
    stored_api, source, monkeypatch
):
    client, _, engine = stored_api
    first = save(client, source).json()
    engine.dispose()
    monkeypatch.setattr(
        main, "read_json", lambda _path: pytest.fail("History must be read from SQL")
    )
    assert client.get(f"/api/experiments/{first['id']}").json() == first


def test_migration_matches_models_and_database_enforces_cascade(stored_api, source):
    client, factory, engine = stored_api
    database.initialize_database()  # Applying head a second time is safe.
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert (
            compare_metadata(MigrationContext.configure(connection), Base.metadata)
            == []
        )
    result = save(client, source).json()
    with factory() as db:
        db.execute(delete(Experiment).where(Experiment.id == result["id"]))
        db.commit()
        assert db.scalar(select(func.count()).select_from(RegionResult)) == 0


def test_database_rejects_inconsistent_integer_counts(stored_api, source):
    client, factory, _ = stored_api
    save(client, source)
    with factory() as db:
        row = db.scalar(select(RegionResult))
        row.water_px = -1
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@pytest.mark.parametrize(
    "mask, boxes",
    [
        (np.zeros((2, 2), dtype=np.uint8), []),
        (np.ones((2, 2), dtype=np.uint8), [[0, 0, 2, 2]]),
    ],
)
def test_empty_fluid_or_empty_complement_is_null(stored_api, source, mask, boxes):
    client, _, _ = stored_api
    source.clear()
    source.update(analysis_result(mask, boxes))
    response = save(client, source)
    assert response.status_code == 201, response.text
    for group in response.json()["composition"].values():
        if group["fluid_area_px"] == 0:
            assert all(value is None for value in group["class_fractions"].values())
            assert group["residual_oil"]["residual_percent"] is None


def test_reject_invalid_payload_pending_or_missing_analysis(
    stored_api, source, monkeypatch
):
    client, factory, _ = stored_api
    for body in (
        {"analysis_id": "../secret"},
        {"analysis_id": source["id"], "water_fraction": 0.2},
        {"analysis_id": source["id"], "name": " "},
    ):
        assert client.post("/api/experiments", json=body).status_code == 422
    source["deadends"][0]["area_px"] = 999
    assert save(client, source).status_code == 422
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Experiment)) == 0
    monkeypatch.setattr(experiments, "get_completed_analysis", ORIGINAL_ANALYSIS_LOADER)
    assert save(client, {"id": "a" * 32}).status_code == 404
    # Use the real bridge for HTTP 404/409, without accepting fabricated class counts.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(main, "job", lambda _id: {"status": "queued"})
        assert save(client, {"id": "a" * 32}).status_code == 409


def prepare_worker(source, monkeypatch):
    folder = main.JOBS / source["id"]
    folder.mkdir()
    monkeypatch.setitem(
        main.active_jobs,
        source["id"],
        {"id": source["id"], "status": "queued", "filename": source["filename"]},
    )
    main.update_job(source["id"])
    monkeypatch.setitem(
        sys.modules,
        "ALGORITHMS.core.pipeline",
        SimpleNamespace(
            run_analysis=lambda _image, _folder, progress: progress("composition")
        ),
    )
    monkeypatch.setattr(
        main,
        "completed_payload",
        lambda _id, _folder, _inference, metadata: {
            **copy.deepcopy(source),
            **metadata,
            "status": "completed",
        },
    )
    return folder


def test_background_analysis_is_saved_automatically(stored_api, source, monkeypatch):
    client, _, _ = stored_api
    folder = prepare_worker(source, monkeypatch)
    main.process_job(source["id"], folder / "input.png")
    status = json.loads((folder / "status.json").read_text())
    assert status["status"] == "completed"
    assert status["persistence_status"] == "saved"
    result = client.get(f"/api/experiments/{status['experiment_id']}")
    assert result.status_code == 200
    assert result.json()["analysis_id"] == source["id"]


def test_failed_database_save_preserves_inference_and_can_be_retried(
    stored_api, source, monkeypatch
):
    client, _, _ = stored_api
    folder = prepare_worker(source, monkeypatch)

    def unavailable(*_args, **_kwargs):
        raise OperationalError("offline", {}, Exception("offline"))

    monkeypatch.setattr(main, "save_experiment", unavailable)
    main.process_job(source["id"], folder / "input.png")
    status = json.loads((folder / "status.json").read_text())
    assert status["status"] == "completed"
    assert status["persistence_status"] == "failed"
    assert save(client, source).status_code == 201
    status = json.loads((folder / "status.json").read_text())
    assert status["persistence_status"] == "saved"
    assert "persistence_error" not in status


def test_history_search_covers_names_ids_and_literal_characters(stored_api, source):
    client, _, _ = stored_api
    first = save(client, source, name="Ensaio WAG referência").json()
    source.update(id="c" * 32, filename="amostra%_02.png")
    second = save(client, source, name="Outro ensaio").json()
    for query in ("WAG", first["id"], first["analysis_id"], "micromodelo"):
        response = client.get("/api/experiments", params={"q": query})
        assert response.status_code == 200
        assert [row["id"] for row in response.json()["items"]] == [first["id"]]
    assert (
        client.get("/api/experiments", params={"q": "%_"}).json()["items"][0]["id"]
        == second["id"]
    )
    assert (
        client.get("/api/experiments", params={"q": "%' OR 1=1"}).json()["total"] == 0
    )


def test_history_sorting_and_filter_validation(stored_api, source):
    client, _, _ = stored_api
    first = save(client, source, name="Zeta").json()
    source.clear()
    source.update(analysis_result(boxes=[], analysis_id="c" * 32))
    second = save(client, source, name="Alfa").json()
    for sorting, order, expected in (
        ("name", "asc", second),
        ("name", "desc", first),
        ("deadend_count", "desc", first),
        ("saved_at", "asc", first),
    ):
        response = client.get(
            "/api/experiments", params={"sort_by": sorting, "order": order, "limit": 1}
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["id"] == expected["id"]
    for params in ({"sort_by": "injected_sql"}, {"order": "up"}, {"q": "x" * 513}):
        assert client.get("/api/experiments", params=params).status_code == 422


def test_history_exports_use_database_without_analysis_files(
    stored_api, source, monkeypatch
):
    client, _, _ = stored_api
    saved = save(client, source).json()
    monkeypatch.setattr(
        main, "read_json", lambda _path: pytest.fail("Exports must use SQL")
    )
    exported = client.get(saved["exports"]["json"])
    assert exported.status_code == 200
    assert exported.json() == saved
    assert "attachment" in exported.headers["content-disposition"]
    exported = client.get(saved["exports"]["csv"])
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == 5
    assert [row["scope"] for row in rows] == [
        "full_image",
        "deadends",
        "outside_deadends",
        "deadend",
        "deadend",
    ]
    assert rows[2]["residual_percent"] == "50.0"
    assert rows[3]["x2"] == "3"
    assert rows[0]["experiment_id"] == saved["id"]
    residual = client.get(saved["exports"]["residual_json"])
    assert residual.status_code == 200
    assert residual.json()["outside_deadends"]["residual_percent"] == 50
    assert (
        len(
            list(
                csv.DictReader(
                    io.StringIO(client.get(saved["exports"]["residual_csv"]).text)
                )
            )
        )
        == 5
    )
    assert (
        client.get(f"/api/experiments/{saved['id']}/export?format=xml").status_code
        == 422
    )
    assert client.get("/api/experiments/unknown/export").status_code == 404
    assert client.get("/api/experiments/unknown/residual-oil").status_code == 404


def test_export_wall_only_regions_has_blank_percentages(stored_api, source):
    client, _, _ = stored_api
    source.clear()
    source.update(analysis_result(mask=np.zeros((2, 2), dtype=np.uint8), boxes=[]))
    saved = save(client, source).json()
    rows = list(csv.DictReader(io.StringIO(client.get(saved["exports"]["csv"]).text)))
    assert len(rows) == 3
    assert all(row["oil_fraction"] == row["residual_percent"] == "" for row in rows)
