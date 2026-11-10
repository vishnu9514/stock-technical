from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class TargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    project_id: str = Field(min_length=1, max_length=160)
    kpi_id: str = Field(min_length=1, max_length=80)
    target_value: float | None = None
    direction: str
    thresholds: dict[str, float]
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None = None


class MeasurementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    project_id: str = Field(min_length=1, max_length=160)
    kpi_id: str = Field(min_length=1, max_length=80)
    period_start: AwareDatetime
    period_end: AwareDatetime
    actual_value: float | None = None
    inputs: dict[str, Any] | None = None
    source: str | None = Field(default=None, max_length=200)


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    kpi_id: str
    period_start: datetime
    period_end: datetime
    actual_value: float | None
    status: str
    source: str | None
    inputs: dict[str, Any] | None
    created_at: datetime
