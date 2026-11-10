from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .collectors import collect_github, read_pytest_junit, timestamp_or_none
from .metrics import calculate


def _in_period(value: str | None, start: datetime, end: datetime) -> bool:
    timestamp = timestamp_or_none(value)
    return timestamp is not None and start <= timestamp < end


def _labels(record: dict) -> set[str]:
    return {str(label.get("name", "")).casefold() for label in record.get("labels", [])}


def github_measurements(records: dict, start: datetime, end: datetime) -> list[dict]:
    """Derive only source-backed GitHub measurements for the selected window."""
    source_issues = [issue for issue in records["issues"] if "pull_request" not in issue]
    issues = [issue for issue in source_issues if _in_period(issue.get("created_at"), start, end)]
    bugs = [issue for issue in issues if "bug" in _labels(issue)]
    all_bugs = [issue for issue in source_issues if "bug" in _labels(issue)]
    closed_bugs = [
        issue for issue in all_bugs
        if issue.get("state") == "closed" and _in_period(issue.get("closed_at"), start, end)
    ]
    fixed_bugs = [
        issue for issue in all_bugs
        if issue.get("fixed_in_period") or issue.get("reopened_in_period")
        or (issue.get("state") == "closed" and _in_period(issue.get("closed_at"), start, end))
    ]
    releases = [
        release for release in records["releases"]
        if _in_period(release.get("published_at"), start, end)
    ]
    tasks = issues
    completed_tasks = [
        task for task in source_issues
        if task.get("state") == "closed" and _in_period(task.get("closed_at"), start, end)
    ]
    completed_planned_tasks = [
        task for task in completed_tasks
        if _in_period(task.get("created_at"), start, end)
    ]
    completed_features = [
        task for task in completed_tasks if "feature" in _labels(task) or "enhancement" in _labels(task)
    ]
    rework = [task for task in completed_tasks if "rework" in _labels(task)]
    regressions = [bug for bug in closed_bugs if bug.get("reopened_in_period")]
    production_bugs = [
        issue for issue in bugs
        if _labels(issue) & {"production", "production-defect", "prod"}
    ]
    period_days = (end - start).total_seconds() / 86400

    deployed_runs = [
        run for run in records["workflow_runs"]
        if "deploy" in str(run.get("name", "")).casefold()
        and _in_period(run.get("run_started_at") or run.get("created_at"), start, end)
    ]
    completed_runs = [
        run for run in records["workflow_runs"]
        if run.get("status") == "completed"
        and _in_period(run.get("run_started_at") or run.get("created_at"), start, end)
    ]
    builds = []
    for run in completed_runs:
        started = timestamp_or_none(run.get("run_started_at"))
        completed = timestamp_or_none(run.get("updated_at"))
        workflow_name = str(run.get("name", "")).casefold()
        if ("build" in workflow_name or "ci" in workflow_name) and started and completed:
            builds.append((completed - started).total_seconds())
    deployments = [run for run in deployed_runs if run.get("status") == "completed"]
    successful_deployments = [run for run in deployments if run.get("conclusion") == "success"]
    failed_deployments = [
        run for run in deployments if run.get("conclusion") not in (None, "success", "skipped", "cancelled")
    ]
    lead_times = []
    for run in successful_deployments:
        committed = timestamp_or_none(run.get("commit_timestamp"))
        deployed = timestamp_or_none(run.get("updated_at"))
        if committed and deployed and deployed >= committed:
            lead_times.append((deployed - committed).total_seconds() / 3600)
    review_times = [
        (timestamp_or_none(pull["first_review_at"]) - timestamp_or_none(pull["created_at"])).total_seconds() / 3600
        for pull in records["pull_requests"]
        if pull.get("first_review_at")
        and _in_period(pull["first_review_at"], start, end)
        and timestamp_or_none(pull.get("created_at"))
        and timestamp_or_none(pull["first_review_at"]) >= timestamp_or_none(pull["created_at"])
    ]
    candidates = [
        ("bug_rate", {"total_bugs": len(bugs), "total_releases": len(releases)}),
        ("bug_resolution_time", {"resolution_hours": [
            (timestamp_or_none(issue["closed_at"]) - timestamp_or_none(issue["created_at"])).total_seconds() / 3600
            for issue in closed_bugs
        ]}),
        ("regression_rate", {"reopened_fixed_bugs": len(regressions), "fixed_bugs": len(fixed_bugs)}),
        ("production_defect_rate", {"production_defects": len(production_bugs), "deployments": len(deployments)}),
        ("deployment_frequency", {"successful_deployments": len(successful_deployments), "period_days": period_days}),
        ("lead_time_for_changes", {"lead_time_hours": lead_times}),
        ("pr_review_time", {"review_time_hours": review_times}),
        ("change_failure_rate", {"failed_deployments": len(failed_deployments), "total_deployments": len(deployments)}),
        ("build_time", {"build_duration_seconds": builds}),
        ("cycle_time", {"cycle_time_hours": [
            (timestamp_or_none(task["closed_at"]) - timestamp_or_none(task["created_at"])).total_seconds() / 3600
            for task in completed_tasks
            if timestamp_or_none(task.get("closed_at")) and timestamp_or_none(task.get("created_at"))
        ]}),
        ("task_completion_rate", {"completed_tasks": len(completed_planned_tasks), "planned_tasks": len(tasks)}),
        ("feature_delivery_rate", {"completed_features": len(completed_features), "period_days": period_days}),
        ("rework_rate", {"rework_tasks": len(rework), "completed_tasks": len(completed_tasks)}),
    ]
    return [
        {"kpi_id": kpi_id, "inputs": inputs, "actual_value": actual}
        for kpi_id, inputs in candidates
        if (actual := calculate(kpi_id, inputs)) is not None
    ]


def _submit(api_url: str, project: str, start: datetime, end: datetime, source: str, measurements: list[dict]) -> tuple[int, int]:
    created = skipped = 0
    for measurement in measurements:
        body = json.dumps({
            "project_id": project,
            "kpi_id": measurement["kpi_id"],
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "actual_value": measurement["actual_value"],
            "inputs": measurement["inputs"],
            "source": source,
        }).encode("utf-8")
        request = Request(
            f"{api_url.rstrip('/')}/api/kpis/measurements",
            data=body,
            headers={
                "Content-Type": "application/json",
                **(
                    {"Authorization": f"Bearer {os.environ['KPI_API_KEY']}"}
                    if os.environ.get("KPI_API_KEY")
                    else {}
                ),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30):
                created += 1
        except HTTPError as error:
            if error.code == 409:
                skipped += 1
                continue
            raise RuntimeError(f"KPI API rejected {measurement['kpi_id']}: {error.read().decode()}") from error
        except URLError as error:
            raise RuntimeError(f"KPI API is unavailable: {error.reason}") from error
    return created, skipped


def write_measurements_csv(
    path: str | Path,
    project: str,
    start: datetime,
    end: datetime,
    sources: list[tuple[str, list[dict]]],
) -> int:
    """Append measurements to CSV, skipping periods already present in SQL/CSV."""
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "project_id",
        "kpi_id",
        "period_start",
        "period_end",
        "actual_value",
        "inputs",
        "source",
    )
    existing_keys: set[tuple[str, str, str, str]] = set()
    if csv_path.exists() and csv_path.stat().st_size:
        with csv_path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames != list(fieldnames):
                raise ValueError(f"{csv_path} does not have the expected KPI CSV columns")
            existing_keys = {
                (row["project_id"], row["kpi_id"], row["period_start"], row["period_end"])
                for row in reader
            }

    pending = []
    for source, measurements in sources:
        for measurement in measurements:
            key = (project, measurement["kpi_id"], start.isoformat(), end.isoformat())
            if key in existing_keys:
                continue
            pending.append({
                "project_id": project,
                "kpi_id": measurement["kpi_id"],
                "period_start": key[2],
                "period_end": key[3],
                "actual_value": measurement["actual_value"],
                "inputs": json.dumps(measurement["inputs"], sort_keys=True),
                "source": source,
            })
            existing_keys.add(key)

    if pending:
        with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if csv_file.tell() == 0:
                writer.writeheader()
            writer.writerows(pending)
    return len(pending)


def read_macd_quality_report(path: str | Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8-sig") as csv_file:
        rows = list(csv.DictReader(csv_file))
    summary = next(
        (row for row in rows if row.get("RECORD_TYPE", "").upper() == "SUMMARY"),
        None,
    )
    if summary is None:
        raise ValueError(f"{path} has no SUMMARY record")

    def integer(name: str) -> int:
        try:
            return int(summary[name])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path} has an invalid or missing {name} value") from error

    eligible = integer("TOTAL_ELIGIBLE_STOCKS")
    candidates = (
        (
            "macd_data_completeness",
            {
                "available_macd_snapshots": integer("AVAILABLE_MACD_SNAPSHOTS"),
                "expected_macd_snapshots": integer("EXPECTED_MACD_SNAPSHOTS"),
            },
        ),
        (
            "valid_isin_coverage",
            {
                "valid_isin_symbols": integer("ISIN_PRESENT_COUNT"),
                "eligible_stocks": eligible,
            },
        ),
        (
            "stock_dashboard_coverage",
            {
                "dashboard_stocks": integer("DASHBOARD_STOCKS"),
                "eligible_stocks": eligible,
            },
        ),
    )
    measurements = []
    for kpi_id, inputs in candidates:
        actual = calculate(kpi_id, inputs)
        if actual is not None:
            measurements.append({"kpi_id": kpi_id, "inputs": inputs, "actual_value": actual})
    return measurements


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect source-backed KPI measurements.")
    parser.add_argument("--project", required=True, help="Stable project identifier used in KPI targets.")
    parser.add_argument("--start", required=True, type=date.fromisoformat, help="Inclusive reporting date (YYYY-MM-DD).")
    parser.add_argument("--end", required=True, type=date.fromisoformat, help="Exclusive reporting date (YYYY-MM-DD).")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="KPI API base URL.")
    parser.add_argument("--repository", help="GitHub owner/repository; gh CLI authentication is required.")
    parser.add_argument("--pytest-xml", help="Path to a pytest JUnit XML report.")
    parser.add_argument("--macd-quality-csv", help="Path to data/macd_data_quality_report.csv.")
    parser.add_argument(
        "--csv",
        default="reports/kpi_measurements.csv",
        help="Append collected measurements to this CSV file (default: reports/kpi_measurements.csv).",
    )
    args = parser.parse_args(argv)
    if args.end <= args.start:
        parser.error("--end must be later than --start")
    start = datetime.combine(args.start, time.min, tzinfo=timezone.utc)
    end = datetime.combine(args.end, time.min, tzinfo=timezone.utc)
    count_created = count_skipped = 0
    csv_sources: list[tuple[str, list[dict]]] = []

    if args.repository:
        records = collect_github(args.repository, start, end)
        measurements = github_measurements(records, start, end)
        source = f"github:{args.repository}"
        created, skipped = _submit(args.api, args.project, start, end, source, measurements)
        count_created += created
        count_skipped += skipped
        csv_sources.append((source, measurements))

    if args.pytest_xml:
        report = read_pytest_junit(args.pytest_xml)
        measurements = []
        for kpi_id, inputs in (
            ("test_pass_rate", {key: report[key] for key in ("passed_tests", "total_tests")}),
            ("code_coverage", {key: report[key] for key in ("covered_statements", "total_statements") if key in report}),
        ):
            actual = calculate(kpi_id, inputs)
            if actual is not None:
                measurements.append({"kpi_id": kpi_id, "inputs": inputs, "actual_value": actual})
        source = "pytest_junit_xml"
        created, skipped = _submit(args.api, args.project, start, end, source, measurements)
        count_created += created
        count_skipped += skipped
        csv_sources.append((source, measurements))

    if args.macd_quality_csv:
        measurements = read_macd_quality_report(args.macd_quality_csv)
        source = "macd_data_quality_report"
        created, skipped = _submit(args.api, args.project, start, end, source, measurements)
        count_created += created
        count_skipped += skipped
        csv_sources.append((source, measurements))

    if not args.repository and not args.pytest_xml and not args.macd_quality_csv:
        parser.error("provide at least one source: --repository, --pytest-xml, or --macd-quality-csv")
    csv_count = write_measurements_csv(args.csv, args.project, start, end, csv_sources)
    print(f"Created {count_created} measurements; skipped {count_skipped} existing measurements.")
    print(f"Stored {csv_count} new measurements in {args.csv}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
