from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KpiMaster(Base):
    __tablename__ = "kpi_master"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    area: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    what_it_measures: Mapped[str] = mapped_column(Text, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    frequency: Mapped[str] = mapped_column(String(40), nullable=False)
    data_source: Mapped[str] = mapped_column(Text, nullable=False)
    targets: Mapped[list[KpiTarget]] = relationship(back_populates="kpi")
    measurements: Mapped[list[KpiMeasurement]] = relationship(back_populates="kpi")


class KpiTarget(Base):
    __tablename__ = "kpi_targets"
    __table_args__ = (
        UniqueConstraint("project_id", "kpi_id", "valid_from", name="uq_target_project_kpi_start"),
        Index("ix_kpi_targets_project_valid", "project_id", "valid_from", "valid_to"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False)
    kpi_id: Mapped[str] = mapped_column(ForeignKey("kpi_master.id", ondelete="CASCADE"), nullable=False)
    target_value: Mapped[float | None] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    kpi: Mapped[KpiMaster] = relationship(back_populates="targets")


class KpiMeasurement(Base):
    __tablename__ = "kpi_measurements"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "kpi_id", "period_start", "period_end",
            name="uq_measurement_project_kpi_period",
        ),
        Index("ix_kpi_measurements_project_period", "project_id", "period_start", "period_end"),
        Index("ix_kpi_measurements_kpi_period", "kpi_id", "period_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False)
    kpi_id: Mapped[str] = mapped_column(ForeignKey("kpi_master.id", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    source: Mapped[str | None] = mapped_column(String(200))
    inputs: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    kpi: Mapped[KpiMaster] = relationship(back_populates="measurements")
    alerts: Mapped[list[KpiAlert]] = relationship(back_populates="measurement")


class DevelopmentRelease(Base):
    __tablename__ = "development_releases"
    __table_args__ = (UniqueConstraint("project_id", "release_key", name="uq_release_project_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    release_key: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str | None] = mapped_column(String(100))
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    bugs: Mapped[list[BugTracking]] = relationship(back_populates="release")
    deployments: Mapped[list[DeploymentHistory]] = relationship(back_populates="release")


class BugTracking(Base):
    __tablename__ = "bug_tracking"
    __table_args__ = (UniqueConstraint("project_id", "external_key", name="uq_bug_project_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    external_key: Mapped[str] = mapped_column(String(200), nullable=False)
    release_id: Mapped[int | None] = mapped_column(ForeignKey("development_releases.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_production: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_regression: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    release: Mapped[DevelopmentRelease | None] = relationship(back_populates="bugs")


class DeploymentHistory(Base):
    __tablename__ = "deployment_history"
    __table_args__ = (UniqueConstraint("project_id", "deployment_key", name="uq_deployment_project_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    deployment_key: Mapped[str] = mapped_column(String(200), nullable=False)
    release_id: Mapped[int | None] = mapped_column(ForeignKey("development_releases.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    succeeded: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(String(200))
    commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release: Mapped[DevelopmentRelease | None] = relationship(back_populates="deployments")


class TestExecutionHistory(Base):
    __tablename__ = "test_execution_history"
    __table_args__ = (UniqueConstraint("project_id", "run_key", name="uq_test_project_run"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    run_key: Mapped[str] = mapped_column(String(200), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    passed_tests: Mapped[int | None] = mapped_column(Integer)
    total_tests: Mapped[int | None] = mapped_column(Integer)
    covered_statements: Mapped[int | None] = mapped_column(Integer)
    total_statements: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(200))


class IncidentHistory(Base):
    __tablename__ = "incident_history"
    __table_args__ = (UniqueConstraint("project_id", "incident_key", name="uq_incident_project_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    incident_key: Mapped[str] = mapped_column(String(200), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(200))


class ProjectTask(Base):
    __tablename__ = "project_tasks"
    __table_args__ = (UniqueConstraint("project_id", "external_key", name="uq_task_project_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    external_key: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_feature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_rework: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_technical_debt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    debt_hours: Mapped[float | None] = mapped_column(Float)
    development_hours: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(200))


class KpiAlert(Base):
    __tablename__ = "kpi_alerts"
    __table_args__ = (Index("ix_kpi_alerts_project_created", "project_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(160), nullable=False)
    measurement_id: Mapped[int] = mapped_column(ForeignKey("kpi_measurements.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    measurement: Mapped[KpiMeasurement] = relationship(back_populates="alerts")
