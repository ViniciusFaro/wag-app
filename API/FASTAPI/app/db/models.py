"""Relational experiment records and aggregate/individual region measurements."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utcnow():
    return datetime.now(UTC)


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "image_width > 0 AND image_height > 0 AND analysis_width > 0 AND analysis_height > 0",
            name="positive_dimensions",
        ),
        CheckConstraint(
            "deadend_count >= 0 AND inference_seconds >= 0", name="nonnegative_results"
        ),
        CheckConstraint(
            "coverage_percent >= 0 AND coverage_percent <= 100", name="valid_coverage"
        ),
        Index("ix_experiments_saved_at_id", "saved_at", "id"),
    )

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    analysis_id: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(512), index=True)
    image_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)
    analysis_width: Mapped[int] = mapped_column(Integer)
    analysis_height: Mapped[int] = mapped_column(Integer)
    segmentation_width: Mapped[int | None] = mapped_column(Integer)
    segmentation_height: Mapped[int | None] = mapped_column(Integer)
    inference_seconds: Mapped[float] = mapped_column(Float)
    device: Mapped[str] = mapped_column(String(100))
    deadend_count: Mapped[int] = mapped_column(Integer)
    coverage_percent: Mapped[float] = mapped_column(Float)
    # Variable inference settings and file references accompany queryable SQL metrics.
    parameters: Mapped[dict] = mapped_column(JSON)
    inference: Mapped[dict] = mapped_column(JSON)
    assets: Mapped[dict] = mapped_column(JSON)
    regions: Mapped[list["RegionResult"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RegionResult.id",
    )


class RegionResult(Base):
    __tablename__ = "region_results"
    __table_args__ = (
        UniqueConstraint("experiment_id", "region_key"),
        CheckConstraint(
            "scope IN ('full_image', 'deadends', 'outside_deadends', 'deadend')",
            name="valid_scope",
        ),
        CheckConstraint(
            "area_px = fluid_area_px + excluded_wall_px", name="area_balance"
        ),
        CheckConstraint(
            "fluid_area_px = water_px + oil_px + gas_px", name="fluid_balance"
        ),
        CheckConstraint(
            "water_px >= 0 AND oil_px >= 0 AND gas_px >= 0 AND excluded_wall_px >= 0",
            name="nonnegative_areas",
        ),
        CheckConstraint(
            "residual_oil_gas_px = oil_px + gas_px AND removed_oil_equivalent_px = water_px",
            name="residual_balance",
        ),
        CheckConstraint(
            "(fluid_area_px = 0 AND water_fraction IS NULL AND oil_fraction IS NULL AND gas_fraction IS NULL AND residual_fraction IS NULL AND removed_fraction IS NULL) OR "
            "(fluid_area_px > 0 AND water_fraction IS NOT NULL AND oil_fraction IS NOT NULL AND gas_fraction IS NOT NULL AND residual_fraction IS NOT NULL AND removed_fraction IS NOT NULL "
            "AND water_fraction BETWEEN 0 AND 1 AND oil_fraction BETWEEN 0 AND 1 AND gas_fraction BETWEEN 0 AND 1 "
            "AND residual_fraction BETWEEN 0 AND 1 AND removed_fraction BETWEEN 0 AND 1)",
            name="valid_fractions",
        ),
        CheckConstraint(
            "(scope = 'deadend' AND detection_id IS NOT NULL AND confidence BETWEEN 0 AND 1) OR (scope != 'deadend' AND detection_id IS NULL)",
            name="region_detection",
        ),
        Index("ix_region_results_experiment_scope", "experiment_id", "scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE")
    )
    experiment: Mapped[Experiment] = relationship(back_populates="regions")
    scope: Mapped[str] = mapped_column(String(24))
    region_key: Mapped[str] = mapped_column(String(64))
    detection_id: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    box_xyxy: Mapped[list | None] = mapped_column(JSON)
    pixel_bounds_xyxy: Mapped[list | None] = mapped_column(JSON)
    area_px: Mapped[int] = mapped_column(Integer)
    fluid_area_px: Mapped[int] = mapped_column(Integer)
    excluded_wall_px: Mapped[int] = mapped_column(Integer)
    water_px: Mapped[int] = mapped_column(Integer)
    oil_px: Mapped[int] = mapped_column(Integer)
    gas_px: Mapped[int] = mapped_column(Integer)
    water_fraction: Mapped[float | None] = mapped_column(Float)
    oil_fraction: Mapped[float | None] = mapped_column(Float)
    gas_fraction: Mapped[float | None] = mapped_column(Float)
    residual_oil_gas_px: Mapped[int] = mapped_column(Integer)
    removed_oil_equivalent_px: Mapped[int] = mapped_column(Integer)
    residual_fraction: Mapped[float | None] = mapped_column(Float)
    removed_fraction: Mapped[float | None] = mapped_column(Float)
    assets: Mapped[dict] = mapped_column(JSON)
