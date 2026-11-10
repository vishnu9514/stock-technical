# NSE MACD pipeline

Run the complete Windows pipeline from the repository root:

```powershell
.\venv\Scripts\python.exe scripts\pipeline_macd.py
```

The pipeline updates Bhavcopy and daily history, resolves identifiers, builds
closed weekly/monthly/quarterly bars, recalculates MACD, exports the dashboard,
and validates coverage and representative calculations. Existing daily files are
backed up with a timestamped `.bak` suffix before the updater changes them.
Indicator inputs are similarly backed up only when indicator values or ordering
need to change.

MACD uses the standard formulas on each period's chronological `CLOSE` series:

- `EMA12 = EMA(CLOSE, 12)`
- `EMA26 = EMA(CLOSE, 26)`
- `MACD = EMA12 - EMA26`
- `MACD_SIGNAL = EMA(MACD, 9)`
- `MACD_HIST = MACD - MACD_SIGNAL`

The recursive EMA is `EMA[t] = alpha * value[t] + (1 - alpha) * EMA[t-1]`,
where `alpha = 2 / (period + 1)` and the first valid close seeds the EMA.
Insufficient histories (fewer than 34 valid closes) are retained in the
dashboard but have `NO_DATA` MACD status.
The independent validator samples 20 deterministic stocks, compares each
available timeframe against a separately implemented EMA reference, and checks
that timeframes below the 34-close threshold correctly remain `NO_DATA`.

The dashboard universe is all daily database symbols plus eligible (`EQ`)
symbols found in Bhavcopy. The equity master is an ISIN fallback and coverage
reference, not the sole stock universe. ISIN resolution prefers valid values
from individual stock databases, then Bhavcopy, then the equity master. Valid
conflicts are recorded in the conflict report; an ambiguous identifier is not
silently selected.

Generated files under `data\` include:

- `macd_dashboard.csv`
- `isin_mapping_report.csv` and `isin_conflicts.csv`
- `stock_coverage_report.csv` and `missing_stocks_report.csv`
- `macd_data_quality_report.csv`
- `macd_calculation_report.csv`, `timeframe_build_report.csv`, and
  `update_nse_database_audit.csv`

The engineering KPI collector can store test and MACD quality measurements in
the configured SQL database and CSV output:

```powershell
.\venv\Scripts\python.exe -m kpi.collect `
  --project stock-system `
  --pytest-xml reports\junit.xml `
  --macd-quality-csv data\macd_data_quality_report.csv `
  --start 2026-11-09 --end 2026-11-10 `
  --api http://127.0.0.1:8000
```

The MACD quality inputs produce KPI measurements for dashboard coverage, valid
ISIN coverage, and available MACD snapshots. Measurements are appended to the
default `reports\kpi_measurements.csv` and persisted through the KPI SQL API.
