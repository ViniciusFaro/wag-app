"""Local analysis API. Run with uvicorn API.FASTAPI.app.main:app."""

import json
import logging
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from ALGORITHMS.indicators.oleo_residual_recuperacao import (
    residual_oil_csv,
    residual_oil_report,
    with_residual_oil,
)

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "ALGORITHMS/data/results"
JOBS = RESULTS / "web"
JOBS.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="LabMEMS · Análise de micromodelos", version="0.1.0")
app.mount("/api/files", StaticFiles(directory=RESULTS), name="analysis-files")
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
lock = threading.Lock()
active_jobs = {}
logger = logging.getLogger(__name__)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def asset_url(path):
    return "/api/files/" + quote(path.relative_to(RESULTS).as_posix(), safe="/")


def completed_payload(job_id, folder, inference_folder, metadata):
    analysis = read_json(folder / "composition.json")
    inference = read_json(inference_folder / "report.json")
    manifest = read_json(folder / "deadends/manifest.json")
    is_sample = job_id == "sample"
    items = [
        {
            **with_residual_oil(item),
            "assets": {
                key: asset_url(folder / "deadends" / path)
                for key, path in item["assets"].items()
            },
        }
        for item in manifest["items"]
    ]
    return {
        **metadata,
        "id": job_id,
        "status": "completed",
        "stage": "completed",
        "image_size_wh": inference["original_size_wh"],
        "analysis_size_wh": analysis["analysis_size_wh"],
        "inference_seconds": inference["total_seconds"],
        "device": inference["device"],
        "deadend_count": analysis["deadend_count"],
        "coverage_percent": analysis["box_union_image_percent"],
        "composition": {
            "full_image": with_residual_oil(analysis["full_image"]),
            "deadends": with_residual_oil(analysis["inside_deadend_boxes"]),
        },
        "assets": {
            "original": "/api/sample-image"
            if is_sample
            else asset_url(folder / "original.png"),
            "segmentation": asset_url(
                inference_folder
                / ("segmentation_aligned.png" if is_sample else "segmentation.png")
            ),
            "detection": asset_url(inference_folder / "detections.png"),
            "overlay": asset_url(inference_folder / "overlay.png"),
            "mask": asset_url(inference_folder / "segmentation_ids.png"),
            "report": asset_url(folder / "composition.json"),
            "csv": asset_url(folder / "per_deadend.csv"),
            "residual_report": f"/api/analyses/{job_id}/residual-oil?format=json",
            "residual_csv": f"/api/analyses/{job_id}/residual-oil?format=csv",
        },
        "deadends": items,
    }


def update_job(job_id, **fields):
    with lock:
        active_jobs[job_id].update(fields)
        (JOBS / job_id / "status.json").write_text(
            json.dumps(active_jobs[job_id]), encoding="utf-8"
        )


def process_job(job_id, image_path):
    try:
        from ALGORITHMS.core.pipeline import run_analysis

        update_job(job_id, status="processing", stage="segmentation")
        run_analysis(
            image_path,
            JOBS / job_id / "analysis",
            lambda stage: update_job(job_id, stage=stage),
        )
        update_job(job_id, status="completed", stage="completed")
    except Exception:
        logger.exception("Analysis failed: %s", job_id)
        update_job(
            job_id,
            status="failed",
            stage="failed",
            error="Não foi possível concluir a análise. Consulte o terminal do servidor Python para ver os detalhes.",
        )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "models_available": all(
            path.is_file()
            for path in [
                ROOT / "MODELS/unet/dcaunet_ema_combined_loss_weighted.pt",
                ROOT / "MODELS/yolo/best.pt",
            ]
        ),
    }


@app.get("/api/sample-image")
def sample_image():
    path = ROOT / "ALGORITHMS/data/raw/train.png"
    if not path.is_file():
        raise HTTPException(404, "A imagem de exemplo não está disponível.")
    return FileResponse(path)


@app.get("/api/analyses/sample")
def sample():
    try:
        return completed_payload(
            "sample",
            RESULTS / "deadend_analysis",
            RESULTS / "inference_test",
            {"filename": "train.png", "is_sample": True},
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            404,
            "A análise de exemplo não está disponível. Execute primeiro os scripts de inferência e análise.",
        ) from exc


@app.post("/api/analyses", status_code=202)
async def upload(image: Annotated[UploadFile, File()]):
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        raise HTTPException(422, "Selecione uma imagem PNG, JPG, TIFF ou WebP.")
    data = await image.read(25 * 1024 * 1024 + 1)
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "A imagem deve ter no máximo 25 MB.")
    from io import BytesIO

    try:
        with Image.open(BytesIO(data)) as decoded:
            if decoded.width * decoded.height > 40_000_000:
                raise HTTPException(
                    422, "Selecione uma imagem com no máximo 40 megapixels."
                )
            decoded.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(
            422, "Não foi possível abrir este arquivo como uma imagem."
        ) from exc
    job_id = uuid.uuid4().hex
    folder = JOBS / job_id
    folder.mkdir()
    path = folder / ("input" + suffix)
    path.write_bytes(data)
    metadata = {
        "id": job_id,
        "filename": Path(image.filename).name,
        "status": "queued",
        "stage": "queued",
        "created_at": datetime.now(UTC).isoformat(),
        "is_sample": False,
    }
    with lock:
        active_jobs[job_id] = metadata
    update_job(job_id)
    executor.submit(process_job, job_id, path)
    return metadata


@app.get("/api/analyses/{job_id}/residual-oil")
def export_residual_oil(job_id: str, format: Literal["json", "csv"] = "json"):
    """Calculate from saved counts, including runs created before this indicator."""
    result = sample() if job_id == "sample" else job(job_id)
    if result["status"] != "completed":
        raise HTTPException(
            409, "A análise precisa estar concluída para exportar os indicadores."
        )
    report = residual_oil_report(
        result["composition"]["full_image"],
        result["composition"]["deadends"],
        result["deadends"],
    )
    content = (
        residual_oil_csv(report)
        if format == "csv"
        else json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    )
    return Response(
        content=content,
        media_type="text/csv" if format == "csv" else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="oleo_residual_{job_id}.{format}"'
        },
    )


@app.get("/api/analyses/{job_id}")
def job(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(404, "Análise não encontrada.")
    path = JOBS / job_id / "status.json"
    if not path.is_file():
        raise HTTPException(404, "Análise não encontrada.")
    with lock:
        metadata = read_json(path)
        running_here = job_id in active_jobs
    if metadata["status"] in {"queued", "processing"} and not running_here:
        return {
            **metadata,
            "status": "failed",
            "error": "O servidor foi reiniciado durante a análise. Envie a imagem novamente.",
        }
    if metadata["status"] == "completed":
        folder = JOBS / job_id / "analysis"
        return completed_payload(job_id, folder, folder, metadata)
    return metadata
