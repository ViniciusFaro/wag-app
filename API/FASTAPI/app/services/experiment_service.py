"""Transactional persistence. Numerical results remain readable without files."""

import csv
import io
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ALGORITHMS.indicators.fluid_composition import (
    CLASS_NAMES,
    composition_from_counts,
    outside_deadend_composition,
)
from ALGORITHMS.indicators.oleo_residual_recuperacao import RESIDUAL_FIELDS

from ..db.models import Experiment, RegionResult

AGGREGATE_SCOPES = ("full_image", "deadends", "outside_deadends")


def as_utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def find_by_analysis(db: Session, analysis_id: str):
    return db.scalar(
        select(Experiment)
        .where(Experiment.analysis_id == analysis_id)
        .options(selectinload(Experiment.regions))
    )


def region_record(scope, key, source):
    # Recompute all fractions from integer counts, including legacy results.
    data = composition_from_counts(source["class_pixels"], source["excluded_wall_px"])
    if any(
        source.get(field, data[field]) != data[field]
        for field in ("area_px", "fluid_area_px")
    ):
        raise ValueError("Inconsistent region areas")
    residual = data["residual_oil"]
    fluid = data["fluid_area_px"]
    individual = scope == "deadend"
    return RegionResult(
        scope=scope,
        region_key=key,
        detection_id=source["detection_id"] if individual else None,
        confidence=source["confidence"] if individual else None,
        box_xyxy=source["box_xyxy"] if individual else None,
        pixel_bounds_xyxy=source["pixel_bounds_xyxy"] if individual else None,
        area_px=data["area_px"],
        fluid_area_px=fluid,
        excluded_wall_px=data["excluded_wall_px"],
        **{f"{name.lower()}_px": data["class_pixels"][name] for name in CLASS_NAMES},
        **{
            f"{name.lower()}_fraction": data["class_fractions"][name]
            for name in CLASS_NAMES
        },
        residual_oil_gas_px=residual["residual_oil_gas_px"],
        removed_oil_equivalent_px=residual["removed_oil_equivalent_px"],
        residual_fraction=residual["residual_oil_gas_px"] / fluid if fluid else None,
        removed_fraction=residual["removed_oil_equivalent_px"] / fluid
        if fluid
        else None,
        assets=source.get("assets", {}),
    )


def save_experiment(db: Session, result: dict, *, name=None, notes=None):
    """Save one complete snapshot atomically; analysis_id makes retries idempotent."""
    existing = find_by_analysis(db, result["id"])
    if existing is not None:
        return existing, False
    if result["status"] != "completed":
        raise ValueError("Only completed analyses can be saved")
    groups = result["composition"]
    outside = outside_deadend_composition(groups["full_image"], groups["deadends"])
    groups = {**groups, "outside_deadends": outside}
    width, height = result["analysis_size_wh"]
    if groups["full_image"]["area_px"] != width * height:
        raise ValueError("Composition does not match the analysis resolution")
    if result["deadend_count"] != len(result["deadends"]):
        raise ValueError("Dead-end count does not match individual regions")
    mask_size = result.get("segmentation_size_wh")
    experiment = Experiment(
        analysis_id=result["id"],
        name=name or result["filename"][:200],
        notes=notes,
        filename=result["filename"],
        image_sha256=result.get("image_sha256"),
        is_sample=result.get("is_sample", False),
        created_at=as_utc(result.get("created_at")),
        completed_at=as_utc(result.get("completed_at")),
        image_width=result["image_size_wh"][0],
        image_height=result["image_size_wh"][1],
        analysis_width=width,
        analysis_height=height,
        segmentation_width=mask_size[0] if mask_size else None,
        segmentation_height=mask_size[1] if mask_size else None,
        inference_seconds=result["inference_seconds"],
        device=result["device"],
        deadend_count=result["deadend_count"],
        coverage_percent=result["coverage_percent"],
        parameters=result.get("parameters", {}),
        inference=result.get("inference", {}),
        assets=result["assets"],
    )
    experiment.regions = [
        region_record(scope, scope, groups[scope]) for scope in AGGREGATE_SCOPES
    ]
    for region in result["deadends"]:
        x1, y1, x2, y2 = region["pixel_bounds_xyxy"]
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("Invalid dead-end pixel bounds")
        if region["area_px"] != (x2 - x1) * (y2 - y1):
            raise ValueError("Dead-end area does not match its bounds")
        experiment.regions.append(region_record("deadend", region["id"], region))
    db.add(experiment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A manual save may race the background worker after inference completes.
        existing = find_by_analysis(db, result["id"])
        if existing is None:
            raise
        return existing, False
    db.refresh(experiment)
    return experiment, True


def region_payload(region):
    result = composition_from_counts(
        {name: getattr(region, f"{name.lower()}_px") for name in CLASS_NAMES},
        region.excluded_wall_px,
    )
    if region.scope == "deadend":
        x1, y1, x2, y2 = region.pixel_bounds_xyxy
        result.update(
            id=region.region_key,
            detection_id=region.detection_id,
            confidence=region.confidence,
            box_xyxy=region.box_xyxy,
            pixel_bounds_xyxy=region.pixel_bounds_xyxy,
            size_wh=[x2 - x1, y2 - y1],
            assets=region.assets,
        )
    return result


def experiment_payload(experiment, *, detail=True):
    aggregates = {
        region.scope: region_payload(region)
        for region in experiment.regions
        if region.scope != "deadend"
    }
    result = {
        "id": experiment.id,
        "analysis_id": experiment.analysis_id,
        "name": experiment.name,
        "filename": experiment.filename,
        "is_sample": experiment.is_sample,
        "created_at": as_utc(experiment.created_at),
        "completed_at": as_utc(experiment.completed_at),
        "saved_at": as_utc(experiment.saved_at),
        "image_size_wh": [experiment.image_width, experiment.image_height],
        "analysis_size_wh": [experiment.analysis_width, experiment.analysis_height],
        "segmentation_size_wh": [
            experiment.segmentation_width,
            experiment.segmentation_height,
        ]
        if experiment.segmentation_width is not None
        else None,
        "inference_seconds": experiment.inference_seconds,
        "device": experiment.device,
        "deadend_count": experiment.deadend_count,
        "coverage_percent": experiment.coverage_percent,
        "composition": aggregates,
    }
    if detail:
        result.update(
            notes=experiment.notes,
            image_sha256=experiment.image_sha256,
            assets=experiment.assets,
            parameters=experiment.parameters,
            inference=experiment.inference,
            deadends=[
                region_payload(region)
                for region in experiment.regions
                if region.scope == "deadend"
            ],
            exports={
                "json": f"/api/experiments/{experiment.id}/export?format=json",
                "csv": f"/api/experiments/{experiment.id}/export?format=csv",
                "residual_json": f"/api/experiments/{experiment.id}/residual-oil?format=json",
                "residual_csv": f"/api/experiments/{experiment.id}/residual-oil?format=csv",
            },
        )
    return result


def experiment_csv(result):
    """One row per aggregate or individual region, with explicit units/scopes."""
    stream = io.StringIO(newline="")
    fields = [
        "experiment_id",
        "analysis_id",
        "scope",
        "region_id",
        "detection_id",
        "confidence",
        "area_px",
        "fluid_area_px",
        "excluded_wall_px",
        "water_fraction",
        "oil_fraction",
        "gas_fraction",
        "x1",
        "y1",
        "x2",
        "y2",
        *RESIDUAL_FIELDS,
    ]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    regions = [(scope, data) for scope, data in result["composition"].items()]
    regions.extend(("deadend", data) for data in result["deadends"])
    for scope, data in regions:
        bounds = data.get("pixel_bounds_xyxy", [None] * 4)
        writer.writerow(
            {
                "experiment_id": result["id"],
                "analysis_id": result["analysis_id"],
                "scope": scope,
                "region_id": data.get("id", scope),
                "detection_id": data.get("detection_id"),
                "confidence": data.get("confidence"),
                **{
                    key: data[key]
                    for key in ("area_px", "fluid_area_px", "excluded_wall_px")
                },
                **{
                    f"{name.lower()}_fraction": data["class_fractions"][name]
                    for name in CLASS_NAMES
                },
                **dict(zip(("x1", "y1", "x2", "y2"), bounds)),
                **data["residual_oil"],
            }
        )
    return stream.getvalue()
