from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_session
from .metrics import DEFINITION_BY_ID, DEFINITIONS, Direction, Status, calculate, classify, score
from .models import KpiAlert, KpiMaster, KpiMeasurement, KpiTarget
from .schemas import MeasurementCreate, MeasurementOut, TargetCreate

app = FastAPI(title="Software Development KPI API", version="1.0.0")


@app.middleware("http")
async def require_configured_api_key(request: Request, call_next):
    api_key = os.environ.get("KPI_API_KEY")
    if api_key and request.url.path.startswith("/api/kpis"):
        provided = request.headers.get("authorization", "")
        if not hmac.compare_digest(provided, f"Bearer {api_key}"):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing KPI API key"})
    return await call_next(request)


def _target_for(session: Session, project_id: str, kpi_id: str, at: datetime) -> KpiTarget | None:
    return session.scalar(
        select(KpiTarget)
        .where(
            KpiTarget.project_id == project_id,
            KpiTarget.kpi_id == kpi_id,
            KpiTarget.valid_from <= at,
            (KpiTarget.valid_to.is_(None)) | (KpiTarget.valid_to >= at),
        )
        .order_by(KpiTarget.valid_from.desc())
        .limit(1)
    )


def _measurement_dict(session: Session, row: KpiMeasurement) -> dict[str, Any]:
    target = _target_for(session, row.project_id, row.kpi_id, row.period_end)
    status = classify(row.actual_value, target.direction, target.thresholds) if target else Status.NO_DATA
    return {
        "id": row.id,
        "project_id": row.project_id,
        "kpi_id": row.kpi_id,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "actual_value": row.actual_value,
        "target_value": target.target_value if target else None,
        "status": status.value,
        "direction": target.direction if target else None,
        "source": row.source,
        "inputs": row.inputs,
        "created_at": row.created_at,
    }


def _latest_measurements(
    session: Session,
    project_id: str | None,
    start: datetime | None,
    end: datetime | None,
) -> list[KpiMeasurement]:
    query = select(KpiMeasurement).order_by(KpiMeasurement.period_end.desc())
    if project_id:
        query = query.where(KpiMeasurement.project_id == project_id)
    if start:
        query = query.where(KpiMeasurement.period_end >= start)
    if end:
        query = query.where(KpiMeasurement.period_end <= end)
    return list(session.scalars(query))


def _aggregate_trend(kpi_id: str, rows: list[KpiMeasurement]) -> float | None:
    definition = DEFINITION_BY_ID[kpi_id]
    if all(row.inputs for row in rows):
        if definition.average_field:
            samples = []
            for row in rows:
                values = row.inputs.get(definition.average_field)
                if not isinstance(values, list):
                    break
                samples.extend(values)
            else:
                return calculate(kpi_id, {definition.average_field: samples})
        elif definition.denominator:
            try:
                inputs = {
                    definition.numerator: sum(row.inputs[definition.numerator] for row in rows),
                    definition.denominator: sum(row.inputs[definition.denominator] for row in rows),
                }
                return calculate(kpi_id, inputs)
            except (KeyError, TypeError):
                pass

    values = [row.actual_value for row in rows if row.actual_value is not None]
    return sum(values) / len(values) if values else None


@app.get("/api/kpis")
def list_kpis(
    project_id: str | None = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    definitions = list(session.scalars(select(KpiMaster).order_by(KpiMaster.area, KpiMaster.name)))
    rows = _latest_measurements(session, project_id, start, end)
    latest: dict[tuple[str, str], KpiMeasurement] = {}
    for row in rows:
        latest.setdefault((row.project_id, row.kpi_id), row)
    projects = {project_id} if project_id else {row.project_id for row in rows}

    result = []
    for definition in definitions:
        for project in sorted(projects):
            row = latest.get((project, definition.id))
            if row:
                result.append({**_measurement_dict(session, row), "name": definition.name, "area": definition.area})
    return result


@app.get("/api/kpis/catalog")
def catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "area": item.area,
            "name": item.name,
            "description": item.description,
            "what_it_measures": item.what_it_measures,
            "formula": item.formula,
            "direction": item.direction.value,
            "frequency": item.frequency,
            "data_source": item.data_source,
        }
        for item in DEFINITIONS
    ]


@app.get("/api/kpis/dashboard")
def dashboard(
    project_id: str | None = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    definitions = list(session.scalars(select(KpiMaster)))
    rows = _latest_measurements(session, project_id, start, end)
    latest: dict[tuple[str, str], KpiMeasurement] = {}
    latest_any_project: dict[str, KpiMeasurement] = {}
    for row in rows:
        latest.setdefault((row.project_id, row.kpi_id), row)
        latest_any_project.setdefault(row.kpi_id, row)
    projects = {project_id} if project_id else {"All projects"}

    items = []
    for definition in definitions:
        for project in sorted(projects):
            row = (
                latest.get((project, definition.id))
                if project_id
                else latest_any_project.get(definition.id)
            )
            if row:
                project = row.project_id
                target = _target_for(session, project, definition.id, row.period_end)
                item = _measurement_dict(session, row)
                actual, period_end = row.actual_value, row.period_end
            else:
                target = _target_for(
                    session,
                    project,
                    definition.id,
                    end or datetime.now(timezone.utc),
                )
                actual, period_end = None, None
                item = {
                    "id": None,
                    "project_id": project,
                    "kpi_id": definition.id,
                    "actual_value": None,
                    "target_value": target.target_value if target else None,
                    "status": Status.NO_DATA.value,
                    "direction": target.direction if target else None,
                    "source": None,
                    "inputs": None,
                    "created_at": None,
                }
            items.append({
                **item,
                "period_end": period_end,
                "name": definition.name,
                "area": definition.area,
                "score": score(actual, target.target_value, target.direction) if target else None,
            })

    statuses = [Status(item["status"]) for item in items]
    area_scores: dict[str, float | None] = {}
    for area in {definition.area for definition in definitions}:
        values = [item["score"] for item in items if item["area"] == area and item["score"] is not None]
        area_scores[area] = sum(values) / len(values) if values else None
    return {
        "total_kpis": len(definitions),
        "excellent_kpis": statuses.count(Status.EXCELLENT),
        "warning_kpis": statuses.count(Status.WARNING),
        "critical_kpis": statuses.count(Status.CRITICAL),
        "area_scores": area_scores,
        "measurements": items,
    }


@app.get("/api/kpis/trends")
def trends(
    project_id: str = Query(min_length=1),
    kpi_id: str | None = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
    period: str = Query(default="weekly", pattern="^(weekly|monthly)$"),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(KpiMeasurement).where(KpiMeasurement.project_id == project_id)
    if kpi_id:
        query = query.where(KpiMeasurement.kpi_id == kpi_id)
    if start:
        query = query.where(KpiMeasurement.period_end >= start)
    if end:
        query = query.where(KpiMeasurement.period_end <= end)
    rows = list(session.scalars(query.order_by(KpiMeasurement.period_end)))
    grouped: dict[tuple[str, str], list[KpiMeasurement]] = {}
    for row in rows:
        date = row.period_end.date()
        if period == "weekly":
            date = date.fromordinal(date.toordinal() - date.weekday())
        else:
            date = date.replace(day=1)
        grouped.setdefault((row.kpi_id, date.isoformat()), []).append(row)
    return [
        {
            "kpi_id": key[0],
            "period": key[1],
            "actual_value": _aggregate_trend(key[0], group),
            "measurement_count": len(group),
        }
        for key, group in sorted(grouped.items())
    ]


@app.get("/api/kpis/alerts")
def alerts(
    project_id: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(KpiAlert).order_by(KpiAlert.created_at.desc())
    if project_id:
        query = query.where(KpiAlert.project_id == project_id)
    return [
        {
            "id": alert.id,
            "project_id": alert.project_id,
            "measurement_id": alert.measurement_id,
            "status": alert.status,
            "message": alert.message,
            "acknowledged_at": alert.acknowledged_at,
            "created_at": alert.created_at,
        }
        for alert in session.scalars(query)
    ]


@app.get("/api/kpis/{kpi_id}")
def get_kpi(
    kpi_id: str,
    project_id: str | None = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    definition = session.get(KpiMaster, kpi_id)
    if not definition:
        raise HTTPException(status_code=404, detail="KPI not found")
    query = select(KpiMeasurement).where(KpiMeasurement.kpi_id == kpi_id).order_by(KpiMeasurement.period_end.desc())
    if project_id:
        query = query.where(KpiMeasurement.project_id == project_id)
    if start:
        query = query.where(KpiMeasurement.period_end >= start)
    if end:
        query = query.where(KpiMeasurement.period_end <= end)
    return {
        "id": definition.id,
        "area": definition.area,
        "name": definition.name,
        "description": definition.description,
        "what_it_measures": definition.what_it_measures,
        "formula": definition.formula,
        "direction": definition.direction,
        "frequency": definition.frequency,
        "data_source": definition.data_source,
        "measurements": [_measurement_dict(session, row) for row in session.scalars(query)],
    }


@app.post("/api/kpis/measurements", response_model=MeasurementOut, status_code=201)
def create_measurement(payload: MeasurementCreate, session: Session = Depends(get_session)) -> KpiMeasurement:
    if payload.period_end <= payload.period_start:
        raise HTTPException(status_code=422, detail="period_end must be after period_start")
    definition = session.get(KpiMaster, payload.kpi_id)
    if not definition:
        raise HTTPException(status_code=404, detail="KPI not found; initialize and seed the database first")
    actual = payload.actual_value
    if actual is None:
        actual = calculate(payload.kpi_id, payload.inputs)
    if actual is not None and actual < 0:
        raise HTTPException(status_code=422, detail="actual_value cannot be negative")
    if actual is not None and payload.kpi_id in {
        "test_pass_rate", "code_coverage", "regression_rate", "change_failure_rate",
        "system_uptime", "error_rate", "task_completion_rate", "rework_rate",
        "technical_debt", "documentation_coverage", "macd_data_completeness",
        "valid_isin_coverage", "stock_dashboard_coverage",
    } and actual > 100:
        raise HTTPException(status_code=422, detail="percentage KPI values cannot exceed 100")
    target = _target_for(session, payload.project_id, payload.kpi_id, payload.period_end)
    status = classify(actual, target.direction, target.thresholds) if target else Status.NO_DATA
    measurement = KpiMeasurement(
        project_id=payload.project_id,
        kpi_id=payload.kpi_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        actual_value=actual,
        status=status.value,
        source=payload.source,
        inputs=payload.inputs,
    )
    session.add(measurement)
    try:
        session.flush()
        if status in (Status.WARNING, Status.CRITICAL):
            session.add(KpiAlert(
                project_id=payload.project_id,
                measurement_id=measurement.id,
                status=status.value,
                message=f"{definition.name} is {status.value.lower()} for the reporting period.",
            ))
        session.commit()
        session.refresh(measurement)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A measurement already exists for this KPI, project, and period") from error
    return measurement


@app.post("/api/kpis/targets", status_code=201)
def create_target(payload: TargetCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    if payload.valid_to is not None and payload.valid_to < payload.valid_from:
        raise HTTPException(status_code=422, detail="valid_to must not be before valid_from")
    if payload.direction not in (Direction.HIGHER.value, Direction.LOWER.value):
        raise HTTPException(status_code=422, detail="direction must be 'higher' or 'lower'")
    if set(payload.thresholds) != {"excellent", "good", "warning"}:
        raise HTTPException(status_code=422, detail="thresholds must define excellent, good, and warning")
    try:
        ordered = [float(payload.thresholds[key]) for key in ("excellent", "good", "warning")]
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail="thresholds must be numeric") from error
    if not all(isfinite(value) for value in ordered):
        raise HTTPException(status_code=422, detail="thresholds must be finite")
    if payload.direction == Direction.HIGHER and not ordered[0] >= ordered[1] >= ordered[2]:
        raise HTTPException(status_code=422, detail="higher-is-better thresholds must descend from excellent to warning")
    if payload.direction == Direction.LOWER and not ordered[0] <= ordered[1] <= ordered[2]:
        raise HTTPException(status_code=422, detail="lower-is-better thresholds must ascend from excellent to warning")
    definition = session.get(KpiMaster, payload.kpi_id)
    if not definition:
        raise HTTPException(status_code=404, detail="KPI not found; initialize and seed the database first")
    if payload.direction != definition.direction:
        raise HTTPException(status_code=422, detail=f"{definition.name} is configured as a {definition.direction}-is-better KPI")

    target = KpiTarget(
        project_id=payload.project_id,
        kpi_id=payload.kpi_id,
        target_value=payload.target_value,
        direction=payload.direction,
        thresholds=payload.thresholds,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    session.add(target)
    try:
        session.commit()
        session.refresh(target)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A target already exists for this project, KPI, and effective date") from error
    return {
        "id": target.id,
        "project_id": target.project_id,
        "kpi_id": target.kpi_id,
        "target_value": target.target_value,
        "direction": target.direction,
        "thresholds": target.thresholds,
        "valid_from": target.valid_from,
        "valid_to": target.valid_to,
    }
