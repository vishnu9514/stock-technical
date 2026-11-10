from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from kpi.api import app
from kpi.database import get_session, initialize_database
from kpi.models import Base


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    initialize_database(session)

    def override_session():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_target_and_measurement_api_validate_classify_and_reject_duplicates(client):
    now = datetime.now(timezone.utc)
    target_response = client.post(
        "/api/kpis/targets",
        json={
            "project_id": "sample",
            "kpi_id": "test_pass_rate",
            "target_value": 95,
            "direction": "higher",
            "thresholds": {"excellent": 98, "good": 95, "warning": 80},
            "valid_from": now.isoformat(),
        },
    )
    assert target_response.status_code == 201

    payload = {
        "project_id": "sample",
        "kpi_id": "test_pass_rate",
        "period_start": now.isoformat(),
        "period_end": (now + timedelta(days=1)).isoformat(),
        "inputs": {"passed_tests": 95, "total_tests": 100},
        "source": "pytest",
    }
    response = client.post("/api/kpis/measurements", json=payload)
    assert response.status_code == 201
    assert response.json()["actual_value"] == 95
    assert response.json()["status"] == "GOOD"
    assert client.post("/api/kpis/measurements", json=payload).status_code == 409


def test_missing_source_data_is_stored_as_no_data(client):
    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/kpis/measurements",
        json={
            "project_id": "sample",
            "kpi_id": "test_pass_rate",
            "period_start": now.isoformat(),
            "period_end": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    assert response.json()["actual_value"] is None
    assert response.json()["status"] == "NO_DATA"


def test_dashboard_has_catalog_total_and_recomputes_status_from_target(client):
    now = datetime.now(timezone.utc)
    client.post(
        "/api/kpis/targets",
        json={
            "project_id": "sample",
            "kpi_id": "test_pass_rate",
            "target_value": 95,
            "direction": "higher",
            "thresholds": {"excellent": 98, "good": 95, "warning": 80},
            "valid_from": now.isoformat(),
        },
    )
    client.post(
        "/api/kpis/measurements",
        json={
            "project_id": "sample",
            "kpi_id": "test_pass_rate",
            "period_start": now.isoformat(),
            "period_end": (now + timedelta(days=1)).isoformat(),
            "actual_value": 95,
        },
    )
    response = client.get("/api/kpis/dashboard", params={"project_id": "sample"})
    assert response.status_code == 200
    data = response.json()
    assert data["total_kpis"] == 25
    assert len(data["measurements"]) == 25
    assert data["measurements"][0]["status"] == "NO_DATA"
    test_pass = next(item for item in data["measurements"] if item["kpi_id"] == "test_pass_rate")
    assert test_pass["status"] == "GOOD"
    assert test_pass["target_value"] == 95
    target_only = client.post(
        "/api/kpis/targets",
        json={
            "project_id": "sample-with-target",
            "kpi_id": "test_pass_rate",
            "target_value": 90,
            "direction": "higher",
            "thresholds": {"excellent": 95, "good": 90, "warning": 75},
            "valid_from": now.isoformat(),
        },
    )
    assert target_only.status_code == 201
    no_measurements = client.get("/api/kpis/dashboard", params={"project_id": "sample-with-target"})
    assert no_measurements.status_code == 200
    no_measurements = no_measurements.json()["measurements"]
    assert all(item["status"] == "NO_DATA" for item in no_measurements)
    test_pass = next(item for item in no_measurements if item["kpi_id"] == "test_pass_rate")
    assert test_pass["target_value"] == 90


def test_invalid_target_direction_and_period_are_rejected(client):
    now = datetime.now(timezone.utc)
    target_response = client.post(
        "/api/kpis/targets",
        json={
            "project_id": "sample",
            "kpi_id": "test_pass_rate",
            "direction": "higher",
            "thresholds": {"excellent": 50, "good": 75, "warning": 60},
            "valid_from": now.isoformat(),
        },
    )
    assert target_response.status_code == 422
    measurement_response = client.post(
        "/api/kpis/measurements",
        json={
            "project_id": "sample",
            "kpi_id": "test_pass_rate",
            "period_start": (now + timedelta(days=1)).isoformat(),
            "period_end": now.isoformat(),
        },
    )
    assert measurement_response.status_code == 422


def test_configured_api_key_protects_kpi_routes(monkeypatch):
    monkeypatch.setenv("KPI_API_KEY", "local-test-key")
    with TestClient(app) as test_client:
        assert test_client.get("/api/kpis/catalog").status_code == 401
        response = test_client.get(
            "/api/kpis/catalog",
            headers={"Authorization": "Bearer local-test-key"},
        )
        assert response.status_code == 200


def test_trend_api_groups_measurements_by_week(client):
    now = datetime.now(timezone.utc)
    for offset, passed in ((0, 9), (7, 8)):
        start = now - timedelta(days=offset + 2)
        end = now - timedelta(days=offset + 1)
        response = client.post(
            "/api/kpis/measurements",
            json={
                "project_id": "sample",
                "kpi_id": "test_pass_rate",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "inputs": {"passed_tests": passed, "total_tests": 10},
            },
        )
        assert response.status_code == 201
    trend = client.get(
        "/api/kpis/trends",
        params={"project_id": "sample", "kpi_id": "test_pass_rate", "period": "weekly"},
    )
    assert trend.status_code == 200
    assert all(item["actual_value"] is not None for item in trend.json())


def test_rate_trend_aggregates_raw_counts_instead_of_averaging_percentages(client):
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    for day, passed, total in ((0, 9, 10), (1, 1, 2)):
        period_start = start + timedelta(days=day)
        response = client.post(
            "/api/kpis/measurements",
            json={
                "project_id": "sample",
                "kpi_id": "test_pass_rate",
                "period_start": period_start.isoformat(),
                "period_end": (period_start + timedelta(hours=12)).isoformat(),
                "inputs": {"passed_tests": passed, "total_tests": total},
            },
        )
        assert response.status_code == 201
    trend = client.get(
        "/api/kpis/trends",
        params={"project_id": "sample", "kpi_id": "test_pass_rate", "period": "weekly"},
    )
    assert trend.status_code == 200
    assert len(trend.json()) == 1
    assert trend.json()[0]["actual_value"] == pytest.approx(100 * 10 / 12)
