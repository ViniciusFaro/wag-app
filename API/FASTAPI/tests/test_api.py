"""Verify upload validation and the real frontend response contract."""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from API.FASTAPI.app import main

client = TestClient(main.app)


def test_sample_contract_and_downloadable_masks():
    response = client.get("/api/analyses/sample")
    if response.status_code == 404:
        pytest.skip("Local sample assets are not present")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    assert result["deadend_count"] == len(result["deadends"])
    for group in result["composition"].values():
        assert sum(group["class_fractions"].values()) == pytest.approx(1)
    for url in result["assets"].values():
        assert client.get(url).status_code == 200
    for url in result["deadends"][0]["assets"].values():
        assert client.get(url).status_code == 200


def test_invalid_upload_is_rejected():
    assert (
        client.post(
            "/api/analyses", files={"image": ("bad.svg", b"<svg/>", "image/svg+xml")}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/analyses", files={"image": ("bad.png", b"not an image", "image/png")}
        ).status_code
        == 422
    )


def test_valid_upload_creates_pollable_job(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "JOBS", tmp_path)
    data = BytesIO()
    Image.new("RGB", (16, 16)).save(data, format="PNG")
    with patch.object(main.executor, "submit") as submit:
        response = client.post(
            "/api/analyses",
            files={"image": ("image.png", data.getvalue(), "image/png")},
        )
        assert response.status_code == 202
        result = response.json()
        assert submit.call_count == 1
        assert client.get(f"/api/analyses/{result['id']}").json()["status"] == "queued"
    main.active_jobs.pop(result["id"])


def test_unknown_job_returns_404():
    assert client.get("/api/analyses/invalid").status_code == 404
