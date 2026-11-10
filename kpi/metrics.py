from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any, Mapping


class Direction(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"


class Status(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    NO_DATA = "NO_DATA"


@dataclass(frozen=True)
class KpiDefinition:
    id: str
    area: str
    name: str
    description: str
    what_it_measures: str
    formula: str
    direction: Direction
    frequency: str
    data_source: str
    numerator: str
    denominator: str | None = None
    multiplier: float = 1.0
    average_field: str | None = None


DEFINITIONS = (
    KpiDefinition("bug_rate", "Software Quality", "Bug Rate", "Bugs per release.", "Defects introduced or found per release.", "total_bugs / total_releases", Direction.LOWER, "Per release", "GitHub issues; bug_tracking; development_releases", "total_bugs", "total_releases"),
    KpiDefinition("defect_density", "Software Quality", "Defect Density", "Defects per 1,000 lines of code.", "Defects relative to codebase size.", "defects / lines_of_code * 1000", Direction.LOWER, "Per release", "GitHub issues; source-control LOC scan", "defects", "lines_of_code", 1000),
    KpiDefinition("bug_resolution_time", "Software Quality", "Bug Resolution Time", "Average elapsed time to resolve bugs, in hours.", "Bug-fix turnaround time.", "average(resolution_hours)", Direction.LOWER, "Weekly", "GitHub issue timestamps; bug_tracking", "resolution_hours", average_field="resolution_hours"),
    KpiDefinition("test_pass_rate", "Software Quality", "Test Pass Rate", "Passed tests as a percentage of executed tests.", "Automated test health.", "passed_tests / total_tests * 100", Direction.HIGHER, "Per test run", "Pytest JUnit XML; test_execution_history", "passed_tests", "total_tests", 100),
    KpiDefinition("code_coverage", "Software Quality", "Code Coverage", "Covered statements as a percentage of measured statements.", "Tested code proportion.", "covered_statements / total_statements * 100", Direction.HIGHER, "Per test run", "Coverage XML; test_execution_history", "covered_statements", "total_statements", 100),
    KpiDefinition("macd_data_completeness", "Software Quality", "MACD Data Completeness", "Available stock/timeframe MACD snapshots as a percentage of expected snapshots.", "Completeness of the D/W/M/3M MACD dataset.", "available_macd_snapshots / expected_macd_snapshots * 100", Direction.HIGHER, "Per pipeline run", "MACD data-quality report", "available_macd_snapshots", "expected_macd_snapshots", 100),
    KpiDefinition("valid_isin_coverage", "Software Quality", "Valid ISIN Coverage", "Stocks with a resolved valid ISIN as a percentage of eligible stocks.", "Coverage and validity of stock identity mapping.", "valid_isin_symbols / eligible_stocks * 100", Direction.HIGHER, "Per pipeline run", "ISIN mapping and MACD data-quality reports", "valid_isin_symbols", "eligible_stocks", 100),
    KpiDefinition("stock_dashboard_coverage", "Software Quality", "Stock Dashboard Coverage", "Eligible stocks represented in the MACD dashboard as a percentage of the eligible universe.", "Whether all eligible stock symbols are accounted for in the dashboard.", "dashboard_stocks / eligible_stocks * 100", Direction.HIGHER, "Per pipeline run", "Stock coverage and MACD dashboard reports", "dashboard_stocks", "eligible_stocks", 100),
    KpiDefinition("regression_rate", "Software Quality", "Regression Rate", "Reopened fixed bugs as a percentage of fixed bugs.", "Previously resolved defects that recur.", "reopened_fixed_bugs / fixed_bugs * 100", Direction.LOWER, "Monthly", "GitHub issue history; bug_tracking", "reopened_fixed_bugs", "fixed_bugs", 100),
    KpiDefinition("production_defect_rate", "Software Quality", "Production Defect Rate", "Post-deployment defects per deployment.", "Defects discovered after release.", "production_defects / deployments", Direction.LOWER, "Per release", "GitHub issues; deployment_history", "production_defects", "deployments"),
    KpiDefinition("deployment_frequency", "Development Speed", "Deployment Frequency", "Successful deployments per day in the reporting period.", "Delivery cadence.", "successful_deployments / period_days", Direction.HIGHER, "Weekly", "GitHub Actions; deployment_history", "successful_deployments", "period_days"),
    KpiDefinition("lead_time_for_changes", "Development Speed", "Lead Time for Changes", "Average time from commit to production, in hours.", "Time from code integration to deployment.", "average(lead_time_hours)", Direction.LOWER, "Weekly", "GitHub commits and Actions; deployment_history", "lead_time_hours", average_field="lead_time_hours"),
    KpiDefinition("cycle_time", "Development Speed", "Cycle Time", "Average task start-to-completion time, in hours.", "Active work duration.", "average(cycle_time_hours)", Direction.LOWER, "Weekly", "GitHub issues/projects; project_tasks", "cycle_time_hours", average_field="cycle_time_hours"),
    KpiDefinition("pr_review_time", "Development Speed", "PR Review Time", "Average pull request open-to-first-review time, in hours.", "Review turnaround time.", "average(review_time_hours)", Direction.LOWER, "Weekly", "GitHub pull requests and reviews", "review_time_hours", average_field="review_time_hours"),
    KpiDefinition("build_time", "Development Speed", "Build Time", "Average build duration, in seconds.", "Build execution time.", "average(build_duration_seconds)", Direction.LOWER, "Per build", "GitHub Actions; build logs", "build_duration_seconds", average_field="build_duration_seconds"),
    KpiDefinition("feature_delivery_rate", "Development Speed", "Feature Delivery Rate", "Completed features per day in the reporting period.", "Feature throughput.", "completed_features / period_days", Direction.HIGHER, "Monthly", "GitHub issues/projects; project_tasks", "completed_features", "period_days"),
    KpiDefinition("change_failure_rate", "Reliability and Performance", "Change Failure Rate", "Failed deployments as a percentage of all deployments.", "Deployment changes requiring remediation.", "failed_deployments / total_deployments * 100", Direction.LOWER, "Weekly", "GitHub Actions; deployment_history", "failed_deployments", "total_deployments", 100),
    KpiDefinition("mttr", "Reliability and Performance", "Mean Time to Recovery", "Average incident recovery time, in minutes.", "Service restoration speed.", "average(recovery_minutes)", Direction.LOWER, "Monthly", "Incident logs; incident_history", "recovery_minutes", average_field="recovery_minutes"),
    KpiDefinition("api_response_time", "Reliability and Performance", "API Response Time", "Average API response latency, in milliseconds.", "Request latency.", "average(response_time_ms)", Direction.LOWER, "Daily", "Application/API performance logs", "response_time_ms", average_field="response_time_ms"),
    KpiDefinition("system_uptime", "Reliability and Performance", "System Uptime", "Available time as a percentage of scheduled time.", "Service availability.", "available_minutes / scheduled_minutes * 100", Direction.HIGHER, "Monthly", "Application monitoring logs", "available_minutes", "scheduled_minutes", 100),
    KpiDefinition("error_rate", "Reliability and Performance", "Error Rate", "Failed requests as a percentage of all requests.", "Application request failure proportion.", "failed_requests / total_requests * 100", Direction.LOWER, "Daily", "Application monitoring logs", "failed_requests", "total_requests", 100),
    KpiDefinition("task_completion_rate", "Engineering Productivity", "Task Completion Rate", "Completed tasks as a percentage of planned tasks.", "Planned work completion.", "completed_tasks / planned_tasks * 100", Direction.HIGHER, "Weekly", "GitHub issues/projects; project_tasks", "completed_tasks", "planned_tasks", 100),
    KpiDefinition("rework_rate", "Engineering Productivity", "Rework Rate", "Tasks requiring rework as a percentage of completed tasks.", "Work that needed correction or repetition.", "rework_tasks / completed_tasks * 100", Direction.LOWER, "Monthly", "GitHub issues/projects; project_tasks", "rework_tasks", "completed_tasks", 100),
    KpiDefinition("technical_debt", "Engineering Productivity", "Technical Debt", "Debt remediation hours as a percentage of total development hours.", "Estimated maintenance burden relative to engineering effort.", "debt_hours / development_hours * 100", Direction.LOWER, "Monthly", "GitHub technical-debt issues; project_tasks", "debt_hours", "development_hours", 100),
    KpiDefinition("documentation_coverage", "Engineering Productivity", "Documentation Coverage", "Documented components as a percentage of tracked components.", "Coverage of required component documentation.", "documented_components / total_components * 100", Direction.HIGHER, "Monthly", "Repository documentation inventory", "documented_components", "total_components", 100),
)

DEFINITION_BY_ID = {definition.id: definition for definition in DEFINITIONS}


def calculate(kpi_id: str, inputs: Mapping[str, Any] | None) -> float | None:
    """Return a measured value, or None when inputs are missing or invalid."""
    definition = DEFINITION_BY_ID.get(kpi_id)
    if definition is None or not inputs:
        return None

    try:
        if definition.average_field:
            values = inputs.get(definition.average_field)
            if not isinstance(values, (list, tuple)) or not values:
                return None
            numbers = [float(value) for value in values]
            if not all(isfinite(value) and value >= 0 for value in numbers):
                return None
            result = sum(numbers) / len(numbers)
        else:
            if definition.denominator is None:
                return None
            numerator = inputs.get(definition.numerator)
            denominator = inputs.get(definition.denominator)
            if numerator is None or denominator is None:
                return None
            numerator, denominator = float(numerator), float(denominator)
            if (
                not isfinite(numerator)
                or not isfinite(denominator)
                or numerator < 0
                or denominator <= 0
                or (
                    definition.multiplier == 100
                    and kpi_id in {
                        "test_pass_rate", "code_coverage", "regression_rate",
                        "change_failure_rate", "system_uptime", "error_rate",
                        "rework_rate", "documentation_coverage",
                        "macd_data_completeness", "valid_isin_coverage",
                        "stock_dashboard_coverage",
                    }
                    and numerator > denominator
                )
            ):
                return None
            result = numerator / denominator * definition.multiplier
    except (TypeError, ValueError, OverflowError):
        return None

    return result if isfinite(result) else None


def classify(
    actual: float | None,
    direction: Direction | str | None,
    thresholds: Mapping[str, Any] | None,
) -> Status:
    """Classify against explicitly configured, direction-aware thresholds."""
    if actual is None or direction is None or not thresholds:
        return Status.NO_DATA
    try:
        actual = float(actual)
        excellent = float(thresholds["excellent"])
        good = float(thresholds["good"])
        warning = float(thresholds["warning"])
        direction = Direction(direction)
    except (KeyError, TypeError, ValueError):
        return Status.NO_DATA
    if not all(isfinite(value) for value in (actual, excellent, good, warning)):
        return Status.NO_DATA

    if direction == Direction.HIGHER:
        if excellent < good or good < warning:
            return Status.NO_DATA
        if actual >= excellent:
            return Status.EXCELLENT
        if actual >= good:
            return Status.GOOD
        if actual >= warning:
            return Status.WARNING
    else:
        if excellent > good or good > warning:
            return Status.NO_DATA
        if actual <= excellent:
            return Status.EXCELLENT
        if actual <= good:
            return Status.GOOD
        if actual <= warning:
            return Status.WARNING
    return Status.CRITICAL


def score(actual: float | None, target: float | None, direction: Direction | str) -> float | None:
    """Return a target-relative, capped score; never score without a target."""
    if actual is None or target is None:
        return None
    try:
        actual, target, direction = float(actual), float(target), Direction(direction)
        if not isfinite(actual) or not isfinite(target) or (direction == Direction.HIGHER and target <= 0):
            return None
        if direction == Direction.HIGHER:
            ratio = actual / target
        elif target == 0:
            ratio = 1.0 if actual <= 0 else 0.0
        else:
            ratio = target / actual if actual > 0 else 1.0
        return max(0.0, min(100.0, ratio * 100))
    except (TypeError, ValueError, ZeroDivisionError):
        return None
