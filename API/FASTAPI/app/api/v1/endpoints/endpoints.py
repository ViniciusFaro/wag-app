"""Experiment GET, POST and DELETE routes for persisted analysis results."""

import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from ALGORITHMS.indicators.oleo_residual_recuperacao import (
    residual_oil_csv,
    residual_oil_report,
)

from ....db.models import Experiment, RegionResult
from ....db.session import get_db
from ....schemas.experiment import ExperimentDetail, ExperimentPage, SaveExperiment
from ....services.experiment_service import (
    as_utc,
    experiment_csv,
    experiment_payload,
    find_by_analysis,
    save_experiment,
)

router = APIRouter(prefix="/api/experiments", tags=["Experimentos"])
Database = Annotated[Session, Depends(get_db)]


def get_completed_analysis(analysis_id):
    # The existing inference routes remain the bridge to legacy on-disk analyses.
    from .... import main

    result = main.sample() if analysis_id == "sample" else main.job(analysis_id)
    if result["status"] != "completed":
        raise HTTPException(
            409, "A análise precisa estar concluída antes de ser salva."
        )
    return result


@router.post("", response_model=ExperimentDetail, status_code=201)
def create_experiment(body: SaveExperiment, response: Response, db: Database):
    existing = find_by_analysis(db, body.analysis_id)
    if existing is not None:
        response.status_code = 200
        return experiment_payload(existing)
    try:
        result = get_completed_analysis(body.analysis_id)
        experiment, created = save_experiment(
            db, result, name=body.name, notes=body.notes
        )
    except (KeyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            422, "Os arquivos da análise contêm dados incompletos ou inconsistentes."
        ) from exc
    response.status_code = 201 if created else 200
    response.headers["Location"] = f"/api/experiments/{experiment.id}"
    from .... import main

    main.mark_persistence(
        body.analysis_id, experiment_id=experiment.id, persistence_status="saved"
    )
    return experiment_payload(experiment)


@router.get("", response_model=ExperimentPage)
def list_experiments(
    db: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    filename: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    analysis_id: Annotated[
        str | None, Query(pattern=r"^(sample|[0-9a-f]{32})$")
    ] = None,
    saved_from: datetime | None = None,
    saved_until: datetime | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    sort_by: Literal["saved_at", "created_at", "name", "deadend_count"] = "saved_at",
    order: Literal["asc", "desc"] = "desc",
):
    if saved_from and saved_until and as_utc(saved_from) > as_utc(saved_until):
        raise HTTPException(422, "A data inicial deve ser anterior à data final.")
    filters = []
    if q:
        filters.append(
            or_(
                *(
                    column.icontains(q, autoescape=True)
                    for column in (
                        Experiment.name,
                        Experiment.filename,
                        Experiment.id,
                        Experiment.analysis_id,
                    )
                )
            )
        )
    if filename:
        filters.append(Experiment.filename.icontains(filename, autoescape=True))
    if analysis_id:
        filters.append(Experiment.analysis_id == analysis_id)
    if saved_from:
        filters.append(Experiment.saved_at >= as_utc(saved_from))
    if saved_until:
        filters.append(Experiment.saved_at <= as_utc(saved_until))
    total = db.scalar(select(func.count()).select_from(Experiment).where(*filters))
    sort_column = getattr(Experiment, sort_by)
    sorting = sort_column.asc() if order == "asc" else sort_column.desc()
    rows = db.scalars(
        select(Experiment)
        .where(*filters)
        .order_by(sorting, Experiment.id.desc())
        .offset(offset)
        .limit(limit)
        .options(
            selectinload(Experiment.regions),
            with_loader_criteria(RegionResult, RegionResult.scope != "deadend"),
        )
    ).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [experiment_payload(row, detail=False) for row in rows],
    }


def get_experiment_or_404(db, experiment_id):
    result = db.scalar(
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(selectinload(Experiment.regions))
    )
    if result is None:
        raise HTTPException(404, "Experimento não encontrado.")
    return result


@router.get("/{experiment_id}", response_model=ExperimentDetail)
def read_experiment(experiment_id: str, db: Database):
    return experiment_payload(get_experiment_or_404(db, experiment_id))


@router.get("/{experiment_id}/export")
def export_experiment(
    experiment_id: str, db: Database, format: Literal["json", "csv"] = "json"
):
    """Export SQL results, independently of inference files and job status JSON."""
    result = experiment_payload(get_experiment_or_404(db, experiment_id))
    content = (
        experiment_csv(result)
        if format == "csv"
        else json.dumps(
            ExperimentDetail.model_validate(result).model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )
    return Response(
        content,
        media_type="text/csv" if format == "csv" else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="experimento_{result["id"]}.{format}"'
        },
    )


@router.get("/{experiment_id}/residual-oil")
def export_experiment_residual_oil(
    experiment_id: str, db: Database, format: Literal["json", "csv"] = "json"
):
    result = experiment_payload(get_experiment_or_404(db, experiment_id))
    groups = result["composition"]
    report = residual_oil_report(
        groups["full_image"],
        groups["deadends"],
        result["deadends"],
        groups["outside_deadends"],
    )
    content = (
        residual_oil_csv(report)
        if format == "csv"
        else json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    )
    return Response(
        content,
        media_type="text/csv" if format == "csv" else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="oleo_residual_{result["id"]}.{format}"'
        },
    )


@router.delete("/{experiment_id}", status_code=204)
def delete_experiment(experiment_id: str, db: Database):
    experiment = get_experiment_or_404(db, experiment_id)
    analysis_id = experiment.analysis_id
    db.delete(experiment)
    db.commit()
    # Artifact files are deliberately retained; other views may still use them.
    from .... import main

    main.mark_persistence(analysis_id, experiment_id=None, persistence_status="deleted")
    return Response(status_code=204)
