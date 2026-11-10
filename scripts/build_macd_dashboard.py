from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.isin_mapping import (  # noqa: E402
    ELIGIBLE_SERIES,
    clean_isin,
    load_isin_from_bhavcopy,
    load_isin_from_equity_master,
    normalize_symbol,
    resolve_isin,
    scan_bhavcopy,
    validate_isin,
    validate_symbol_isin_mapping,
)

DATA_DIR = BASE_DIR / "data"
TIMEFRAME_FOLDERS = {
    "M": DATA_DIR / "nse_monthly",
    "W": DATA_DIR / "nse_weekly",
    "D": DATA_DIR / "nse_stocks",
    "3M": DATA_DIR / "nse_quarterly",
}
OUTPUT_FILE = DATA_DIR / "macd_dashboard.csv"
EQUITY_FILE = DATA_DIR / "EQUITY_L.csv"
BHAVCOPY_FOLDER = DATA_DIR / "nse_bhavcopy"
ISIN_MAPPING_REPORT = DATA_DIR / "isin_mapping_report.csv"
ISIN_CONFLICTS_REPORT = DATA_DIR / "isin_conflicts.csv"
MISSING_STOCKS_REPORT = DATA_DIR / "missing_stocks_report.csv"
STOCK_COVERAGE_REPORT = DATA_DIR / "stock_coverage_report.csv"
DATA_QUALITY_REPORT = DATA_DIR / "macd_data_quality_report.csv"

SNAPSHOT_COLUMNS = ["DATE", "CLOSE", "VOLUME", "MACD", "MACD_SIGNAL", "MACD_HIST"]
OUTPUT_COLUMN_NAMES = {
    "DATE": "DATE",
    "CLOSE": "CLOSE",
    "VOLUME": "VOLUME",
    "MACD": "MACD_LINE",
    "MACD_SIGNAL": "MACD_SIGNAL_LINE",
    "MACD_HIST": "MACD_HISTOGRAM",
}
MIN_MACD_PERIODS = 34


def clean_symbol(symbol: object) -> str:
    return normalize_symbol(symbol)


def load_isin_by_symbol(path: str | Path) -> dict[str, set[str]]:
    return load_isin_from_equity_master(path)


def load_latest_snapshot(
    folder: str | Path,
    filename: str,
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    path = Path(folder) / filename
    empty_stats: dict[str, Any] = {
        "invalid_ohlc": 0,
        "invalid_isin": 0,
        "duplicates": 0,
        "isin_values": set(),
    }
    if not path.is_file():
        return None, "file missing", empty_stats
    if path.stat().st_size == 0:
        return None, "empty file", empty_stats
    try:
        frame = pd.read_csv(path)
    except (
        OSError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as error:
        return None, f"unreadable file: {error}", empty_stats
    frame.columns = [str(column).strip().upper() for column in frame.columns]
    stats = empty_stats.copy()
    if "ISIN" in frame:
        raw_isins = frame["ISIN"].map(clean_isin)
        stats["invalid_isin"] = int(
            sum(bool(value) and not validate_isin(value) for value in raw_isins)
        )
        stats["isin_values"] = {value for value in raw_isins if validate_isin(value)}
    required = set(SNAPSHOT_COLUMNS).difference(frame.columns)
    if required:
        return None, f"missing columns: {', '.join(sorted(required))}", stats

    if {"OPEN", "HIGH", "LOW", "CLOSE"}.issubset(frame.columns):
        ohlc = frame[["OPEN", "HIGH", "LOW", "CLOSE"]].apply(
            pd.to_numeric, errors="coerce"
        )
        valid = ohlc.notna().all(axis=1) & (ohlc > 0).all(axis=1)
        valid &= (
            (ohlc["HIGH"] >= ohlc[["OPEN", "LOW", "CLOSE"]].max(axis=1))
            & (ohlc["LOW"] <= ohlc[["OPEN", "HIGH", "CLOSE"]].min(axis=1))
        )
        stats["invalid_ohlc"] = int((~valid).sum())

    frame["DATE"] = pd.to_datetime(frame["DATE"], errors="coerce")
    for column in SNAPSHOT_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["DATE"])
    stats["duplicates"] = int(frame["DATE"].duplicated(keep="last").sum())
    frame = frame.sort_values("DATE").drop_duplicates(subset=["DATE"], keep="last")
    frame = frame.dropna(subset=["CLOSE"])
    if frame.empty:
        return None, "no valid dated CLOSE records", stats

    row = frame.iloc[-1]
    insufficient = len(frame) < MIN_MACD_PERIODS
    snapshot: dict[str, Any] = {
        column: (
            pd.Timestamp(row[column]).strftime("%Y-%m-%d")
            if column == "DATE"
            else (np.nan if insufficient else row[column])
        )
        for column in SNAPSHOT_COLUMNS
    }
    histogram = frame["MACD_HIST"].dropna()
    current_hist = np.nan if insufficient or histogram.empty else float(histogram.iloc[-1])
    previous_hist = (
        float(histogram.iloc[-2])
        if not insufficient and len(histogram) >= 2
        else np.nan
    )
    snapshot["ISIN_CANDIDATES"] = stats["isin_values"]
    snapshot["ZERO_LINE"] = classify_zero_line(snapshot["MACD"])
    snapshot["CROSSOVER"] = classify_crossover(snapshot["MACD"], snapshot["MACD_SIGNAL"])
    snapshot["MOMENTUM"] = classify_momentum(current_hist, previous_hist)
    snapshot["INSUFFICIENT_HISTORY"] = insufficient
    return snapshot, "", stats


def classify_zero_line(macd: object) -> str:
    if pd.isna(macd) or not np.isfinite(float(macd)):
        return "NO_DATA"
    if float(macd) > 0:
        return "ABOVE_ZERO"
    if float(macd) < 0:
        return "BELOW_ZERO"
    return "AT_ZERO"


def classify_crossover(macd: object, signal: object) -> str:
    if (
        pd.isna(macd)
        or pd.isna(signal)
        or not np.isfinite(float(macd))
        or not np.isfinite(float(signal))
    ):
        return "NO_DATA"
    return "Bullish" if float(macd) > float(signal) else "Bearish"


def classify_momentum(current: object, previous: object) -> str:
    if (
        pd.isna(current)
        or pd.isna(previous)
        or not np.isfinite(float(current))
        or not np.isfinite(float(previous))
    ):
        return "NO_DATA"
    if float(current) > float(previous):
        return "RISING"
    if float(current) < float(previous):
        return "FALLING"
    return "UNCHANGED"


def _read_equity_symbols(path: Path) -> set[str]:
    try:
        master = pd.read_csv(path, usecols=lambda name: str(name).strip().upper() == "SYMBOL")
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError, ValueError):
        return set()
    if master.empty:
        return set()
    return {normalize_symbol(value) for value in master.iloc[:, 0] if normalize_symbol(value)}


def _file_symbols(folder: Path) -> set[str]:
    if not folder.is_dir():
        raise FileNotFoundError(f"Required timeframe folder not found: {folder}")
    return {normalize_symbol(path.stem) for path in folder.glob("*.csv")}


def _make_reports(
    rows: list[dict[str, Any]],
    coverage_symbols: set[str],
    eligible_symbols: set[str],
    daily_symbols: set[str],
    series_by_symbol: dict[str, set[str]],
    isin_conflicts: list[dict[str, str]],
    summary: dict[str, Any],
) -> None:
    resolved_mapping = {
        row["SYMBOL"]: row["ISIN"]
        for row in rows
        if row.get("ISIN") != "UNKNOWN"
    }
    isin_conflicts.extend(validate_symbol_isin_mapping(resolved_mapping))
    pd.DataFrame(
        [
            {
                "SYMBOL": row["SYMBOL"],
                "ISIN": row["ISIN"],
                "ISIN_SOURCE": row["ISIN_SOURCE"],
                "ISIN_STATUS": row["ISIN_STATUS"],
            }
            for row in rows
        ],
        columns=["SYMBOL", "ISIN", "ISIN_SOURCE", "ISIN_STATUS"],
    ).to_csv(ISIN_MAPPING_REPORT, index=False)
    pd.DataFrame(
        isin_conflicts,
        columns=["SYMBOL", "ISIN", "SOURCE", "REASON"],
    ).drop_duplicates().to_csv(ISIN_CONFLICTS_REPORT, index=False)

    coverage_rows = []
    missing_rows = []
    for symbol in sorted(coverage_symbols):
        in_daily = symbol in daily_symbols
        in_bhavcopy = symbol in series_by_symbol
        in_timeframes = {
            key: symbol in values
            for key, values in summary["timeframe_symbols"].items()
        }
        in_dashboard = symbol in eligible_symbols
        reasons = []
        if in_bhavcopy and not in_daily:
            reasons.append("eligible Bhavcopy symbol has no daily database")
        for timeframe, exists in in_timeframes.items():
            if in_daily and not exists:
                reasons.append(f"missing {timeframe} timeframe database")
        if in_dashboard and not any(
            row["SYMBOL"] == symbol and row.get("HAS_DATA")
            for row in rows
        ):
            reasons.append("no usable timeframe data")
        if not in_dashboard:
            status = "MASTER_ONLY_NOT_IN_ELIGIBLE_UNIVERSE"
        elif not in_daily:
            status = "MISSING_DAILY_DATABASE"
        elif reasons:
            status = "INCOMPLETE"
        else:
            status = "COMPLETE"
        entry = {
            "SYMBOL": symbol,
            "SERIES": "|".join(sorted(series_by_symbol.get(symbol, set()))),
            "IN_BHAVCOPY": in_bhavcopy,
            "IN_DAILY_DATABASE": in_daily,
            "IN_WEEKLY_DATABASE": in_timeframes.get("W", False),
            "IN_MONTHLY_DATABASE": in_timeframes.get("M", False),
            "IN_QUARTERLY_DATABASE": in_timeframes.get("3M", False),
            "IN_MACD_DASHBOARD": in_dashboard,
            "IN_EQUITY_MASTER": symbol in summary["master_symbols"],
            "STATUS": status,
            "REASON": "; ".join(reasons),
        }
        coverage_rows.append(entry)
        if not in_daily:
            missing_rows.append(entry)

    coverage_columns = [
        "SYMBOL", "SERIES", "IN_BHAVCOPY", "IN_DAILY_DATABASE",
        "IN_WEEKLY_DATABASE", "IN_MONTHLY_DATABASE", "IN_QUARTERLY_DATABASE",
        "IN_MACD_DASHBOARD", "IN_EQUITY_MASTER", "STATUS", "REASON",
    ]
    pd.DataFrame(coverage_rows, columns=coverage_columns).to_csv(
        STOCK_COVERAGE_REPORT, index=False
    )
    pd.DataFrame(missing_rows, columns=coverage_columns).to_csv(
        MISSING_STOCKS_REPORT, index=False
    )

    quality_columns = [
        "RECORD_TYPE", "TOTAL_ELIGIBLE_STOCKS", "DASHBOARD_STOCKS", "TOTAL_PROCESSED_STOCKS",
        "TOTAL_SKIPPED_STOCKS", "MISSING_DAILY_DATA", "MISSING_WEEKLY_DATA",
        "MISSING_MONTHLY_DATA", "MISSING_QUARTERLY_DATA", "ISIN_PRESENT_COUNT",
        "ISIN_UNKNOWN_COUNT", "DUPLICATE_SYMBOLS", "DUPLICATE_ISIN_MAPPINGS",
        "INVALID_ISIN_COUNT", "INVALID_OHLC_RECORDS", "DUPLICATE_DATE_RECORDS",
        "AVAILABLE_MACD_SNAPSHOTS", "EXPECTED_MACD_SNAPSHOTS",
        "LAST_AVAILABLE_TRADING_DATE", "SYMBOL", "REASON",
    ]
    quality_rows = [{
        "RECORD_TYPE": "SUMMARY",
        **{key: value for key, value in summary.items() if key != "timeframe_symbols" and key != "master_symbols"},
    }]
    quality_rows.extend(
        {
            "RECORD_TYPE": "SKIPPED_STOCK",
            "SYMBOL": row["SYMBOL"],
            "REASON": row.get("REASON", ""),
        }
        for row in rows if not row.get("HAS_DATA")
    )
    pd.DataFrame(quality_rows, columns=quality_columns).to_csv(
        DATA_QUALITY_REPORT, index=False
    )


def main() -> None:
    daily_symbols = _file_symbols(TIMEFRAME_FOLDERS["D"])
    timeframe_symbols = {
        key: _file_symbols(folder)
        for key, folder in TIMEFRAME_FOLDERS.items()
    }
    master_symbols = _read_equity_symbols(EQUITY_FILE)
    series_by_symbol, bhavcopy_isins = scan_bhavcopy(BHAVCOPY_FOLDER)
    eligible_bhavcopy_symbols = {
        symbol
        for symbol, series in series_by_symbol.items()
        if series.intersection(ELIGIBLE_SERIES)
    }
    eligible_symbols = daily_symbols | eligible_bhavcopy_symbols
    coverage_symbols = eligible_symbols | master_symbols
    equity_isins = load_isin_by_symbol(EQUITY_FILE) if EQUITY_FILE.is_file() else {}
    stock_isins: dict[str, set[str]] = {}
    results: list[dict[str, Any]] = []
    conflict_rows: list[dict[str, str]] = []
    missing_by_timeframe = {key: 0 for key in ("D", "W", "M", "3M")}
    invalid_isin_count = invalid_ohlc_count = duplicate_date_count = 0
    last_daily_date = ""

    for index, symbol in enumerate(sorted(eligible_symbols), start=1):
        filename = f"{symbol}.csv"
        snapshots: dict[str, dict[str, Any] | None] = {}
        reasons: list[str] = []
        has_data = False
        for timeframe, folder in TIMEFRAME_FOLDERS.items():
            snapshot, reason, stats = load_latest_snapshot(folder, filename)
            snapshots[timeframe] = snapshot
            invalid_isin_count += stats["invalid_isin"]
            invalid_ohlc_count += stats["invalid_ohlc"]
            duplicate_date_count += stats["duplicates"]
            stock_isins.setdefault(symbol, set()).update(stats["isin_values"])
            if snapshot:
                has_data = True
                if timeframe == "D" and snapshot["DATE"] and snapshot["DATE"] > last_daily_date:
                    last_daily_date = snapshot["DATE"]
            else:
                missing_by_timeframe[timeframe] += 1
                reasons.append(f"{timeframe}: {reason}")

        isin, isin_source, isin_status, resolution_conflicts = resolve_isin(
            symbol,
            stock_isins,
            bhavcopy_isins,
            equity_isins,
        )
        conflict_rows.extend(resolution_conflicts)
        result: dict[str, Any] = {
            "SYMBOL": symbol,
            "ISIN": isin,
            "ISIN_SOURCE": isin_source,
            "ISIN_STATUS": isin_status,
            "HAS_DATA": has_data,
            "REASON": "; ".join(reasons),
        }
        statuses: dict[str, str] = {}
        for timeframe in ("M", "W", "D", "3M"):
            snapshot = snapshots[timeframe]
            for column in SNAPSHOT_COLUMNS:
                out_column = f"{timeframe}_{OUTPUT_COLUMN_NAMES[column]}"
                result[out_column] = snapshot[column] if snapshot else np.nan
            for suffix, key in (
                ("MACD_ZERO_LINE", "ZERO_LINE"),
                ("MACD_CROSSOVER", "CROSSOVER"),
                ("MACD_MOMENTUM", "MOMENTUM"),
            ):
                result[f"{timeframe}_{suffix}"] = snapshot[key] if snapshot else "NO_DATA"
            statuses[timeframe] = snapshot["CROSSOVER"] if snapshot else "NO_DATA"
        result["M_MACD"] = statuses["M"]
        result["W_MACD"] = statuses["W"]
        result["D_MACD"] = statuses["D"]
        result["3M_MACD"] = statuses["3M"]
        result["ALIGNMENT_SCORE"] = (
            (statuses["3M"] == "Bullish") * 40
            + (statuses["M"] == "Bullish") * 30
            + (statuses["W"] == "Bullish") * 20
            + (statuses["D"] == "Bullish") * 10
        )
        results.append(result)
        if index % 500 == 0 or index == len(eligible_symbols):
            print(f"Processed {index:,}/{len(eligible_symbols):,} eligible stocks")

    duplicate_symbols = len(results) - len({row["SYMBOL"] for row in results})
    isin_present = sum(row["ISIN"] != "UNKNOWN" for row in results)
    available_macd_snapshots = sum(
        row[f"{timeframe}_MACD_CROSSOVER"] != "NO_DATA"
        for row in results
        for timeframe in ("D", "W", "M", "3M")
    )
    duplicate_isin_count = len(validate_symbol_isin_mapping({
        row["SYMBOL"]: row["ISIN"] for row in results if row["ISIN"] != "UNKNOWN"
    }))
    summary: dict[str, Any] = {
        "TOTAL_ELIGIBLE_STOCKS": len(eligible_symbols),
        "DASHBOARD_STOCKS": len(results),
        "TOTAL_PROCESSED_STOCKS": sum(bool(row["HAS_DATA"]) for row in results),
        "TOTAL_SKIPPED_STOCKS": sum(not bool(row["HAS_DATA"]) for row in results),
        "MISSING_DAILY_DATA": missing_by_timeframe["D"],
        "MISSING_WEEKLY_DATA": missing_by_timeframe["W"],
        "MISSING_MONTHLY_DATA": missing_by_timeframe["M"],
        "MISSING_QUARTERLY_DATA": missing_by_timeframe["3M"],
        "ISIN_PRESENT_COUNT": isin_present,
        "ISIN_UNKNOWN_COUNT": len(results) - isin_present,
        "DUPLICATE_SYMBOLS": duplicate_symbols,
        "DUPLICATE_ISIN_MAPPINGS": duplicate_isin_count,
        "INVALID_ISIN_COUNT": invalid_isin_count,
        "INVALID_OHLC_RECORDS": invalid_ohlc_count,
        "DUPLICATE_DATE_RECORDS": duplicate_date_count,
        "AVAILABLE_MACD_SNAPSHOTS": available_macd_snapshots,
        "EXPECTED_MACD_SNAPSHOTS": len(eligible_symbols) * 4,
        "LAST_AVAILABLE_TRADING_DATE": last_daily_date,
        "timeframe_symbols": timeframe_symbols,
        "master_symbols": master_symbols,
    }
    columns = ["SYMBOL", "ISIN", "ISIN_SOURCE", "ISIN_STATUS"]
    for timeframe in ("M", "W", "D", "3M"):
        columns.extend(
            f"{timeframe}_{OUTPUT_COLUMN_NAMES[column]}"
            for column in SNAPSHOT_COLUMNS
        )
        columns.extend(
            [
                f"{timeframe}_MACD_ZERO_LINE",
                f"{timeframe}_MACD_CROSSOVER",
                f"{timeframe}_MACD_MOMENTUM",
                f"{timeframe}_MACD",
            ]
        )
    columns.extend(["ALIGNMENT_SCORE", "HAS_DATA", "REASON"])
    dashboard = pd.DataFrame(results, columns=columns)
    if dashboard["SYMBOL"].duplicated().any():
        raise RuntimeError("Duplicate symbols detected while assembling the MACD dashboard")
    dashboard = dashboard.sort_values(
        ["ALIGNMENT_SCORE", "SYMBOL"],
        ascending=[False, True],
    )
    dashboard.drop(columns=["HAS_DATA", "REASON"]).to_csv(OUTPUT_FILE, index=False)
    _make_reports(
        results,
        coverage_symbols,
        eligible_symbols,
        daily_symbols,
        series_by_symbol,
        conflict_rows,
        summary,
    )
    if set(dashboard["SYMBOL"]) != eligible_symbols:
        raise RuntimeError("MACD dashboard coverage does not match the eligible stock universe")
    print(f"MACD dashboard: {OUTPUT_FILE} ({len(dashboard):,} eligible stocks)")
    print(f"ISIN mapping: {ISIN_MAPPING_REPORT}")
    print(f"ISIN conflicts: {ISIN_CONFLICTS_REPORT}")
    print(f"Stock coverage: {STOCK_COVERAGE_REPORT}")
    print(f"Missing stocks: {MISSING_STOCKS_REPORT}")
    print(f"MACD data quality: {DATA_QUALITY_REPORT}")
    print(
        "Quality summary: "
        f"processed={summary['TOTAL_PROCESSED_STOCKS']:,}, "
        f"without data={summary['TOTAL_SKIPPED_STOCKS']:,}, "
        f"ISIN present={summary['ISIN_PRESENT_COUNT']:,}, "
        f"ISIN unknown={summary['ISIN_UNKNOWN_COUNT']:,}"
    )


if __name__ == "__main__":
    main()
