from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_pytest_junit(path: str | Path) -> dict[str, Any]:
    """Read pytest's JUnit XML; never infer or synthesize missing coverage."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(suite.get("tests", 0)) for suite in suites)
    failures = sum(int(suite.get("failures", 0)) + int(suite.get("errors", 0)) for suite in suites)
    skipped = sum(int(suite.get("skipped", 0)) for suite in suites)
    result: dict[str, Any] = {
        "total_tests": total,
        "passed_tests": max(0, total - failures - skipped),
        "source": "pytest_junit_xml",
    }

    coverage_path = Path(path).with_name("coverage.xml")
    if coverage_path.is_file():
        coverage_root = ET.parse(coverage_path).getroot()
        lines_covered = coverage_root.get("lines-covered")
        lines_valid = coverage_root.get("lines-valid")
        if lines_covered is not None and lines_valid is not None:
            result["covered_statements"] = int(lines_covered)
            result["total_statements"] = int(lines_valid)
    return result


def read_json_records(path: str | Path) -> list[dict[str, Any]]:
    """Load JSON array, JSON object, or newline-delimited JSON log records."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{path} must contain a JSON object or a list of JSON objects")
    return value


def read_github_records(
    repository: str,
    endpoint: str,
    jq_expression: str = ".[]",
) -> list[dict[str, Any]]:
    """Read a paginated GitHub REST endpoint using the configured gh CLI login."""
    completed = subprocess.run(
        ["gh", "api", "--paginate", endpoint, "--jq", jq_expression],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    try:
        return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise ValueError(f"GitHub returned invalid JSON for {repository}:{endpoint}") from error


def read_github_record(repository: str, endpoint: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["gh", "api", endpoint],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"GitHub returned invalid JSON for {repository}:{endpoint}") from error
    if not isinstance(value, dict):
        raise ValueError(f"GitHub returned an unexpected response for {repository}:{endpoint}")
    return value


def collect_github(
    repository: str,
    start: datetime,
    end: datetime,
) -> dict[str, list[dict[str, Any]]]:
    """Collect timestamped GitHub records and required commit/review metadata."""
    if "/" not in repository or repository.startswith("/") or repository.endswith("/"):
        raise ValueError("repository must be in owner/name format")
    base = f"repos/{repository}"
    issues = read_github_records(repository, f"{base}/issues?state=all&per_page=100")
    pull_requests = read_github_records(repository, f"{base}/pulls?state=all&per_page=100")
    workflow_runs = read_github_records(
        repository,
        f"{base}/actions/runs?created={start.date().isoformat()}..{end.date().isoformat()}&per_page=100",
        ".workflow_runs[]",
    )
    releases = read_github_records(repository, f"{base}/releases?per_page=100")

    for issue in issues:
        updated = _parse_timestamp(issue.get("updated_at"))
        if (
            "pull_request" not in issue
            and "bug" in {str(label.get("name", "")).casefold() for label in issue.get("labels", [])}
            and updated is not None
            and start <= updated < end
        ):
            events = read_github_records(
                repository,
                f"{base}/issues/{issue['number']}/events?per_page=100",
            )
            issue["reopened_in_period"] = any(
                event.get("event") == "reopened"
                and _parse_timestamp(event.get("created_at")) is not None
                and start <= _parse_timestamp(event["created_at"]) < end
                for event in events
            )
            issue["fixed_in_period"] = any(
                event.get("event") == "closed"
                and _parse_timestamp(event.get("created_at")) is not None
                and start <= _parse_timestamp(event["created_at"]) < end
                for event in events
            )

    for pull in pull_requests:
        if _parse_timestamp(pull.get("updated_at")) and start <= _parse_timestamp(pull["updated_at"]) < end:
            reviews = read_github_records(
                repository,
                f"{base}/pulls/{pull['number']}/reviews?per_page=100",
            )
            timestamps = [
                review["submitted_at"]
                for review in reviews
                if review.get("submitted_at")
            ]
            pull["first_review_at"] = min(timestamps) if timestamps else None

    commit_dates: dict[str, str] = {}
    for run in workflow_runs:
        if "deploy" not in str(run.get("name", "")).casefold() or not run.get("head_sha"):
            continue
        sha = run["head_sha"]
        if sha not in commit_dates:
            commit = read_github_record(repository, f"{base}/commits/{sha}")
            commit_dates[sha] = commit.get("commit", {}).get("committer", {}).get("date")
        run["commit_timestamp"] = commit_dates[sha]

    return {
        "issues": issues,
        "pull_requests": pull_requests,
        "workflow_runs": workflow_runs,
        "releases": releases,
    }


def timestamp_or_none(value: str | None) -> datetime | None:
    """Parse UTC timestamps from source records, preserving absent values."""
    parsed = _parse_timestamp(value)
    return parsed.astimezone(timezone.utc) if parsed else None
