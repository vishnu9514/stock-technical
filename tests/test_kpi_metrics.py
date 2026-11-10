import pytest

from kpi.metrics import DEFINITIONS, Direction, Status, calculate, classify, score


@pytest.mark.parametrize(
    ("kpi_id", "inputs", "expected"),
    [
        ("bug_rate", {"total_bugs": 6, "total_releases": 3}, 2),
        ("test_pass_rate", {"passed_tests": 9, "total_tests": 10}, 90),
        ("change_failure_rate", {"failed_deployments": 2, "total_deployments": 8}, 25),
        ("system_uptime", {"available_minutes": 99, "scheduled_minutes": 100}, 99),
        ("task_completion_rate", {"completed_tasks": 7, "planned_tasks": 10}, 70),
        ("bug_resolution_time", {"resolution_hours": [1, 3, 5]}, 3),
    ],
)
def test_formulas(kpi_id, inputs, expected):
    assert calculate(kpi_id, inputs) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("kpi_id", "inputs"),
    [
        ("test_pass_rate", None),
        ("test_pass_rate", {}),
        ("test_pass_rate", {"passed_tests": 2}),
        ("test_pass_rate", {"passed_tests": 2, "total_tests": 0}),
        ("bug_resolution_time", {"resolution_hours": []}),
        ("unknown", {"value": 2}),
    ],
)
def test_missing_or_invalid_source_data_returns_no_data(kpi_id, inputs):
    assert calculate(kpi_id, inputs) is None


@pytest.mark.parametrize(
    ("direction", "actual", "expected"),
    [
        (Direction.HIGHER, 95, Status.EXCELLENT),
        (Direction.HIGHER, 80, Status.GOOD),
        (Direction.HIGHER, 65, Status.WARNING),
        (Direction.HIGHER, 20, Status.CRITICAL),
        (Direction.LOWER, 2, Status.EXCELLENT),
        (Direction.LOWER, 8, Status.GOOD),
        (Direction.LOWER, 15, Status.WARNING),
        (Direction.LOWER, 25, Status.CRITICAL),
    ],
)
def test_status_classification(direction, actual, expected):
    thresholds = (
        {"excellent": 90, "good": 75, "warning": 60}
        if direction == Direction.HIGHER
        else {"excellent": 5, "good": 10, "warning": 20}
    )
    assert classify(actual, direction, thresholds) == expected


def test_missing_or_misordered_targets_are_no_data():
    assert classify(90, Direction.HIGHER, None) == Status.NO_DATA
    assert classify(90, Direction.HIGHER, {"excellent": 70, "good": 80, "warning": 60}) == Status.NO_DATA
    assert classify(None, Direction.LOWER, {"excellent": 1, "good": 2, "warning": 3}) == Status.NO_DATA


def test_target_relative_score_respects_direction():
    assert score(90, 80, Direction.HIGHER) == pytest.approx(100)
    assert score(4, 5, Direction.LOWER) == pytest.approx(100)
    assert score(10, 5, Direction.LOWER) == pytest.approx(50)
    assert score(90, None, Direction.HIGHER) is None


def test_all_requested_kpis_have_explicit_directions_and_sources():
    assert len(DEFINITIONS) == 25
    assert all(item.direction in (Direction.HIGHER, Direction.LOWER) for item in DEFINITIONS)
    assert all(item.data_source.strip() and item.formula.strip() for item in DEFINITIONS)
