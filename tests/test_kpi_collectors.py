import csv
import json
from datetime import datetime, timezone

import pytest

from kpi.collect import (
    github_measurements,
    read_macd_quality_report,
    write_measurements_csv,
)
from kpi.collectors import read_json_records, read_pytest_junit


def test_pytest_junit_counts_passed_failed_and_skipped(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites><testsuite tests="4" failures="1" errors="0" skipped="1"/></testsuites>',
        encoding="utf-8",
    )
    result = read_pytest_junit(report)
    assert result["total_tests"] == 4
    assert result["passed_tests"] == 2
    assert "covered_statements" not in result


def test_pytest_coverage_is_only_included_when_report_exists(tmp_path):
    (tmp_path / "junit.xml").write_text(
        '<testsuite tests="1" failures="0" errors="0" skipped="0"/>',
        encoding="utf-8",
    )
    (tmp_path / "coverage.xml").write_text(
        '<coverage lines-covered="45" lines-valid="60"/>',
        encoding="utf-8",
    )
    assert read_pytest_junit(tmp_path / "junit.xml")["covered_statements"] == 45


def test_json_log_readers_support_object_arrays_and_jsonl(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps([{"status": 200}, {"status": 503}]), encoding="utf-8")
    assert len(read_json_records(path)) == 2
    path.write_text('{"status": 200}\n{"status": 503}\n', encoding="utf-8")
    assert len(read_json_records(path)) == 2


def test_json_log_reader_rejects_non_object_records(tmp_path):
    path = tmp_path / "events.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        read_json_records(path)


def test_github_collection_only_calculates_metrics_with_required_source_data():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 8, tzinfo=timezone.utc)
    records = {
        "issues": [
            {
                "created_at": "2025-12-20T00:00:00Z",
                "closed_at": "2026-01-02T00:00:00Z",
                "state": "closed",
                "labels": [{"name": "bug"}],
                "reopened_in_period": True,
            }
        ],
        "pull_requests": [
            {
                "created_at": "2026-01-02T00:00:00Z",
                "first_review_at": "2026-01-03T00:00:00Z",
            }
        ],
        "releases": [{"published_at": "2026-01-04T00:00:00Z"}],
        "workflow_runs": [
            {
                "name": "deploy",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-01-05T00:00:00Z",
                "run_started_at": "2026-01-05T00:00:00Z",
                "updated_at": "2026-01-05T00:01:00Z",
                "commit_timestamp": "2026-01-04T00:00:00Z",
            }
        ],
    }
    results = {item["kpi_id"]: item["actual_value"] for item in github_measurements(records, start, end)}
    assert results["bug_rate"] == 0
    assert results["deployment_frequency"] == pytest.approx(1 / 7)
    assert results["bug_resolution_time"] == pytest.approx(13 * 24)
    assert results["regression_rate"] == 100
    assert results["lead_time_for_changes"] == pytest.approx(24 + 1 / 60)
    assert results["pr_review_time"] == 24


def test_measurement_csv_appends_values_and_skips_existing_periods(tmp_path):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 8, tzinfo=timezone.utc)
    path = tmp_path / "exports" / "measurements.csv"
    measurements = [{
        "kpi_id": "test_pass_rate",
        "actual_value": 100,
        "inputs": {"passed_tests": 2, "total_tests": 2},
    }]

    assert write_measurements_csv(
        path, "sample", start, end, [("pytest", measurements)]
    ) == 1
    assert write_measurements_csv(
        path, "sample", start, end, [("pytest", measurements)]
    ) == 0

    with path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sample"
    assert rows[0]["actual_value"] == "100"
    assert json.loads(rows[0]["inputs"]) == measurements[0]["inputs"]


def test_macd_quality_report_produces_data_coverage_kpis(tmp_path):
    report = tmp_path / "macd_data_quality_report.csv"
    report.write_text(
        "RECORD_TYPE,TOTAL_ELIGIBLE_STOCKS,DASHBOARD_STOCKS,ISIN_PRESENT_COUNT,"
        "AVAILABLE_MACD_SNAPSHOTS,EXPECTED_MACD_SNAPSHOTS\n"
        "SUMMARY,100,100,90,350,400\n",
        encoding="utf-8",
    )
    results = {row["kpi_id"]: row for row in read_macd_quality_report(report)}
    assert results["macd_data_completeness"]["actual_value"] == 87.5
    assert results["valid_isin_coverage"]["actual_value"] == 90
    assert results["stock_dashboard_coverage"]["actual_value"] == 100
