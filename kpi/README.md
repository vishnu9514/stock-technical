# Software development KPI monitoring

This is an isolated KPI feature for the existing Streamlit project. It does not
change the stock dashboard or its pipelines. The Streamlit page is available at
`pages/KPI_Monitoring.py`; the FastAPI service and PostgreSQL models are in this
directory.

## Setup

Use Python 3.10 or newer. Install the KPI dependencies, configure PostgreSQL,
create the schema, and start the API and existing Streamlit app in separate
terminals:

```powershell
python -m pip install -r kpi\requirements.txt
$env:KPI_DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/stock_system_kpi"
python -m kpi.init_db
uvicorn kpi.api:app --reload
```

In another terminal:

```powershell
python -m streamlit run app.py
```

The KPI page appears in Streamlit's multipage navigation. By default it reads
the API at `http://127.0.0.1:8000`; set `KPI_API_URL` if the API runs elsewhere.
Do not expose the development API publicly without adding deployment-appropriate
authentication, TLS, and network restrictions; the repository has no existing
authentication system to reuse.

`python -m kpi.init_db` creates these indexed, related tables and seeds the KPI
catalog idempotently: `kpi_master`, `kpi_targets`, `kpi_measurements`,
`development_releases`, `bug_tracking`, `deployment_history`,
`test_execution_history`, `incident_history`, `project_tasks`, and `kpi_alerts`.
Measurement uniqueness is enforced by project, KPI, and reporting period.

## Collection

The collector uses the authenticated GitHub CLI (`gh auth login`) for repository
issues, pull requests, releases, and Actions runs. It can also read a pytest
JUnit XML report and an adjacent Cobertura `coverage.xml` report:

```powershell
gh auth status
python -m kpi.collect --project stock-system --repository vishnu9514/stock-technical --start 2026-10-01 --end 2026-11-01
python -m kpi.collect --project stock-system --pytest-xml reports\junit.xml --start 2026-11-03 --end 2026-11-04
python -m kpi.collect --project stock-system --macd-quality-csv data\macd_data_quality_report.csv --start 2026-11-09 --end 2026-11-10
```

Dates are UTC, inclusive at `--start` and exclusive at `--end`. Create separate
measurements for non-overlapping periods; rerunning the same period safely skips
existing records. Measurements are saved in the configured SQL database through
the API and appended to `reports/kpi_measurements.csv` by default. Change the CSV
destination with `--csv path\to\measurements.csv`. CSV rows contain the project,
KPI, reporting period, calculated value, source inputs, and source; reruns do not
duplicate a project/KPI/period row. Targets and classified statuses remain in SQL
and are available through the dashboard API.

GitHub collection uses repository issue labels as conventions:
`bug`, `production`/`production-defect`/`prod`, `feature`/
`enhancement`, and `rework`. Actions workflows with `deploy` in their name are
treated as deployment workflows; completed workflows named `build` or `ci`
contribute build duration. Metrics that cannot be derived from these sources (for example
commit-to-production lead time, first-review latency, LOC-normalized density,
coverage without a coverage report, and monitoring/incident metrics) are not
fabricated. Send them through the measurement API when a real data source is
configured.
Regression measurements use actual GitHub issue `reopened` events, not a label
guess; the denominator is the set of bugs fixed or reopened in that reporting
period.

The weekly GitHub Actions workflow runs tests and collects GitHub/pytest data for
the previous completed UTC week. Configure the repository secret `KPI_API_URL`
and optionally `KPI_API_KEY`, plus the repository variable `KPI_PROJECT_ID`
(defaults to the repository name). If the API has `KPI_API_KEY` set, the same
secret must be provided to the workflow.

`kpi.collectors` also provides parsers for JSON/JSONL monitoring or performance
logs and a paginated GitHub API adapter. The measurement API accepts either an
explicit `actual_value` or the raw formula `inputs`; if the required source
fields are absent, it stores a `NO_DATA` measurement with a null actual value.

## Formula catalog and metric direction

All time values are expressed in the units shown. A missing input, empty sample,
non-finite value, or non-positive denominator produces no calculated value.
Rates use the specified numerator/denominator and are not inferred from unrelated
records.

| Area | KPI | Formula | Better direction |
|---|---|---|---|
| Software Quality | Bug Rate | total bugs / total releases | Lower |
| Software Quality | Defect Density | defects / lines of code * 1,000 | Lower |
| Software Quality | Bug Resolution Time | average resolution hours | Lower |
| Software Quality | Test Pass Rate | passed tests / executed tests * 100 | Higher |
| Software Quality | Code Coverage | covered statements / total statements * 100 | Higher |
| Software Quality | MACD Data Completeness | available stock/timeframe MACD snapshots / expected snapshots * 100 | Higher |
| Software Quality | Valid ISIN Coverage | valid ISIN symbols / eligible stocks * 100 | Higher |
| Software Quality | Stock Dashboard Coverage | dashboard stocks / eligible stocks * 100 | Higher |
| Software Quality | Regression Rate | reopened fixed bugs / fixed bugs * 100 | Lower |
| Software Quality | Production Defect Rate | production defects / deployments | Lower |
| Development Speed | Deployment Frequency | successful deployments / period days | Higher |
| Development Speed | Lead Time for Changes | average commit-to-production hours | Lower |
| Development Speed | Cycle Time | average task start-to-completion hours | Lower |
| Development Speed | PR Review Time | average PR-to-first-review hours | Lower |
| Development Speed | Build Time | average build duration seconds | Lower |
| Development Speed | Feature Delivery Rate | completed features / period days | Higher |
| Reliability and Performance | Change Failure Rate | failed deployments / deployments * 100 | Lower |
| Reliability and Performance | Mean Time to Recovery | average recovery minutes | Lower |
| Reliability and Performance | API Response Time | average response milliseconds | Lower |
| Reliability and Performance | System Uptime | available / scheduled minutes * 100 | Higher |
| Reliability and Performance | Error Rate | failed / total requests * 100 | Lower |
| Engineering Productivity | Task Completion Rate | completed tasks / planned tasks * 100 | Higher |
| Engineering Productivity | Rework Rate | rework tasks / completed tasks * 100 | Lower |
| Engineering Productivity | Technical Debt | debt remediation / development hours * 100 | Lower |
| Engineering Productivity | Documentation Coverage | documented / tracked components * 100 | Higher |

Set project-specific targets using `POST /api/kpis/targets`. Thresholds are
required and must be ordered for the KPI's defined direction:

```json
{
  "project_id": "stock-system",
  "kpi_id": "test_pass_rate",
  "target_value": 95,
  "direction": "higher",
  "thresholds": {"excellent": 98, "good": 95, "warning": 80},
  "valid_from": "2026-11-01T00:00:00Z"
}
```

Without a configured target/threshold set, status is `NO_DATA`; actual values
remain separate from targets. Increasing KPIs require excellent >= good >=
warning; decreasing KPIs require excellent <= good <= warning. Historical status
is evaluated against the target effective at the measurement's period end.
Area scores are capped, direction-aware actual-to-target ratios and are `N/A`
when no target exists; they are not subjective productivity ratings.

## API

- `GET /api/kpis` — latest available values, optionally filtered by project and dates.
- `GET /api/kpis/{kpi_id}` — formula metadata and historical measurements.
- `GET /api/kpis/dashboard` — KPI totals, statuses, target-relative area scores, and measurements.
- `GET /api/kpis/trends?project_id=...&period=weekly|monthly` — grouped historical values.
- `GET /api/kpis/alerts` — warning and critical alerts.
- `POST /api/kpis/measurements` — create a measurement; duplicate project/KPI/period returns 409.
- `POST /api/kpis/targets` — create an effective-dated target and classification thresholds.
- `GET /api/kpis/catalog` — KPI formulas, source descriptions, and directions.

OpenAPI documentation is available at `/docs` while the API is running. Set
`KPI_API_KEY` to require a bearer key for KPI API routes; when unset, the API is
intended for local development behind `127.0.0.1`.

## Tests

```powershell
python -m pytest -q tests\test_kpi_metrics.py tests\test_kpi_collectors.py tests\test_kpi_api.py
```
