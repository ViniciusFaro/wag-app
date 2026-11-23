"""Stable contracts for saving experiments and querying their history."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Fraction = Annotated[float, Field(ge=0, le=1)]
PixelArea = Annotated[int, Field(ge=0)]
Size = tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]]


class SaveExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    analysis_id: str = Field(pattern=r"^(sample|[0-9a-f]{32})$")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=10000)


class ResidualOil(BaseModel):
    water_px: PixelArea
    oil_px: PixelArea
    gas_px: PixelArea
    initial_oil_equivalent_px: PixelArea
    residual_oil_gas_px: PixelArea
    removed_oil_equivalent_px: PixelArea
    initial_oil_equivalent_percent: float | None
    oil_percent: float | None
    gas_percent: float | None
    residual_percent: float | None
    removed_percent: float | None


class RegionComposition(BaseModel):
    area_px: PixelArea
    fluid_area_px: PixelArea
    excluded_wall_px: PixelArea
    class_pixels: dict[Literal["Water", "Oil", "Gas"], PixelArea]
    class_fractions: dict[Literal["Water", "Oil", "Gas"], Fraction | None]
    class_percentages: dict[str, float | None]
    dominant_class: Literal["Water", "Oil", "Gas"] | None
    residual_oil: ResidualOil


class Compositions(BaseModel):
    full_image: RegionComposition
    deadends: RegionComposition
    outside_deadends: RegionComposition


class DeadendResult(RegionComposition):
    id: str
    detection_id: int
    confidence: Fraction
    box_xyxy: tuple[float, float, float, float]
    pixel_bounds_xyxy: tuple[int, int, int, int]
    size_wh: Size
    assets: dict[str, str]


class ExperimentSummary(BaseModel):
    id: str
    analysis_id: str
    name: str
    filename: str
    is_sample: bool
    created_at: datetime | None
    completed_at: datetime | None
    saved_at: datetime
    image_size_wh: Size
    analysis_size_wh: Size
    segmentation_size_wh: Size | None
    inference_seconds: float
    device: str
    deadend_count: int
    coverage_percent: float
    composition: Compositions


class ExperimentDetail(ExperimentSummary):
    notes: str | None
    image_sha256: str | None
    assets: dict[str, str]
    parameters: dict
    inference: dict
    deadends: list[DeadendResult]
    exports: dict[str, str]


class ExperimentPage(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ExperimentSummary]
