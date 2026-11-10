from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.isin_mapping import normalize_symbol, validate_isin  # noqa: E402

DATA_DIR = BASE_DIR / "data"
EXPECTED_20MICRONS_ISIN = "INE144J01027"
TIMEFRAME_INPUTS = {
    "D": DATA_DIR / "nse_stocks",
    "W": DATA_DIR / "nse_weekly",
    "M": DATA_DIR / "nse_monthly",
    "3M": DATA_DIR / "nse_quarterly",
}
MACD_COLUMNS = {
    "D": ("D_MACD_LINE", "D_MACD_SIGNAL_LINE", "D_MACD_HISTOGRAM"),
    "W": ("W_MACD_LINE", "W_MACD_SIGNAL_LINE", "W_MACD_HISTOGRAM"),
    "M": ("M_MACD_LINE", "M_MACD_SIGNAL_LINE", "M_MACD_HISTOGRAM"),
    "3M": ("3M_MACD_LINE", "3M_MACD_SIGNAL_LINE", "3M_MACD_HISTOGRAM"),
}


def _ema(values: list[float], span: int) -> list[float]:
    alpha = 2.0 / (span + 1.0)
    result = []
    current = None
    for value in values:
        current = value if current is None else alpha * value + (1.0 - alpha) * current
        result.append(current)
    return result


def _reference_latest(path: Path) -> tuple[str, tuple[float, float, float]] | None:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip().upper() for column in frame.columns]
    if not {"DATE", "CLOSE"}.issubset(frame.columns):
        return None
    frame["DATE"] = pd.to_datetime(frame["DATE"], errors="coerce")
    frame["CLOSE"] = pd.to_numeric(frame["CLOSE"], errors="coerce")
    frame = frame.dropna(subset=["DATE", "CLOSE"])
    frame = frame.sort_values("DATE").drop_duplicates("DATE", keep="last")
    if len(frame) < 34:
        return None
    closes = frame["CLOSE"].astype(float).tolist()
    macd = [fast - slow for fast, slow in zip(_ema(closes, 12), _ema(closes, 26))]
    signal = _ema(macd, 9)
    return frame.iloc[-1]["DATE"].strftime("%Y-%m-%d"), (
        macd[-1],
        signal[-1],
        macd[-1] - signal[-1],
    )


def _read_dashboard(path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    by_symbol = {normalize_symbol(row["SYMBOL"]): row for row in rows}
    return rows, by_symbol


def _check_macd(row: dict[str, str], symbol: str, timeframe: str) -> bool:
    source = TIMEFRAME_INPUTS[timeframe] / f"{symbol}.csv"
    reference = _reference_latest(source)
    if reference is None:
        if row.get(f"{timeframe}_MACD_CROSSOVER") != "NO_DATA":
            raise RuntimeError(
                f"{symbol} {timeframe} has insufficient history but dashboard does not report NO_DATA"
            )
        populated = [
            column
            for column in MACD_COLUMNS[timeframe]
            if pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").notna().iloc[0]
        ]
        if populated:
            raise RuntimeError(
                f"{symbol} {timeframe} has insufficient history but contains MACD values: {populated}"
            )
        return False
    date, expected = reference
    date_column = f"{timeframe}_DATE"
    if row.get(date_column) != date:
        raise RuntimeError(
            f"{symbol} {timeframe} latest date mismatch: dashboard={row.get(date_column)}, source={date}"
        )
    for column, value in zip(MACD_COLUMNS[timeframe], expected):
        actual = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
        if pd.isna(actual) or not np.isclose(float(actual), value, rtol=1e-10, atol=1e-10):
            raise RuntimeError(
                f"{symbol} {timeframe} {column} mismatch: dashboard={actual}, reference={value}"
            )
    return True


def _select_random_symbols(by_symbol: dict[str, dict[str, str]], count: int = 20) -> list[str]:
    candidates = [
        symbol
        for symbol, row in by_symbol.items()
        if symbol != "20MICRONS"
        and any(
            row.get(f"{timeframe}_MACD_CROSSOVER") != "NO_DATA"
            for timeframe in TIMEFRAME_INPUTS
        )
    ]
    return random.Random(42).sample(candidates, min(count, len(candidates)))


def main() -> None:
    dashboard_path = DATA_DIR / "macd_dashboard.csv"
    coverage_path = DATA_DIR / "stock_coverage_report.csv"
    if not dashboard_path.is_file() or not coverage_path.is_file():
        raise FileNotFoundError("Run build_macd_dashboard.py before validating MACD outputs")
    rows, by_symbol = _read_dashboard(dashboard_path)
    symbols = [normalize_symbol(row["SYMBOL"]) for row in rows]
    if len(symbols) != len(set(symbols)):
        raise RuntimeError("MACD dashboard contains duplicate symbols")

    daily_symbols = {
        normalize_symbol(path.stem)
        for path in TIMEFRAME_INPUTS["D"].glob("*.csv")
    }
    with coverage_path.open(newline="", encoding="utf-8-sig") as file:
        coverage = list(csv.DictReader(file))
    eligible_bhavcopy_symbols = {
        normalize_symbol(row["SYMBOL"])
        for row in coverage
        if row.get("IN_BHAVCOPY", "").casefold() == "true"
        and "EQ" in row.get("SERIES", "").split("|")
    }
    expected_symbols = daily_symbols | eligible_bhavcopy_symbols
    missing = expected_symbols - set(symbols)
    if missing:
        raise RuntimeError(f"Dashboard is missing {len(missing)} eligible symbols: {sorted(missing)[:20]}")

    reference = by_symbol.get("20MICRONS")
    if reference is None or reference.get("ISIN") != EXPECTED_20MICRONS_ISIN:
        raise RuntimeError(
            "20MICRONS dashboard ISIN mismatch: "
            f"{reference.get('ISIN') if reference else 'symbol absent'}"
        )
    for folder in TIMEFRAME_INPUTS.values():
        source = folder / "20MICRONS.csv"
        if not source.is_file():
            raise RuntimeError(f"20MICRONS source file missing: {source}")
        frame = pd.read_csv(source)
        if "ISIN" not in frame or not frame["ISIN"].map(
            lambda value: str(value).strip().upper() == EXPECTED_20MICRONS_ISIN
        ).any():
            raise RuntimeError(f"20MICRONS ISIN is missing or incorrect in {source}")

    if any(
        row.get(f"{timeframe}_DATE")
        and pd.Timestamp(row[f"{timeframe}_DATE"]).normalize() > pd.Timestamp.now().normalize()
        for row in rows
        for timeframe in TIMEFRAME_INPUTS
    ):
        raise RuntimeError("Dashboard includes a future-dated timeframe bar")

    sample = _select_random_symbols(by_symbol)
    comparisons = 0
    for symbol in ["20MICRONS", *sample]:
        for timeframe in TIMEFRAME_INPUTS:
            if _check_macd(by_symbol[symbol], symbol, timeframe):
                comparisons += 1
    if len(sample) < 20:
        raise RuntimeError(f"Only {len(sample)} additional stocks had MACD data; expected 20")

    unknown_isin = sum(row.get("ISIN") == "UNKNOWN" for row in rows)
    invalid_isin = [
        row["SYMBOL"] for row in rows
        if row.get("ISIN") not in {"UNKNOWN", ""} and not validate_isin(row.get("ISIN"))
    ]
    if invalid_isin:
        raise RuntimeError(f"Dashboard contains invalid ISIN values: {invalid_isin[:20]}")
    print(
        "MACD validation passed: "
        f"{len(rows):,} dashboard symbols, {len(missing):,} missing, "
        f"{comparisons} independent timeframe comparisons "
        f"(20MICRONS plus {len(sample)} random stocks; insufficient histories checked for NO_DATA), "
        f"{unknown_isin:,} unresolved ISINs."
    )


if __name__ == "__main__":
    main()
