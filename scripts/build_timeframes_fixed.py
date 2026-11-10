from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.isin_mapping import (  # noqa: E402
    clean_isin,
    load_isin_from_equity_master,
    normalize_symbol,
    resolve_isin,
    scan_bhavcopy,
    validate_isin,
)

DATA_DIR = BASE_DIR / "data"
daily_folder = DATA_DIR / "nse_stocks"
weekly_folder = DATA_DIR / "nse_weekly"
monthly_folder = DATA_DIR / "nse_monthly"
quarterly_folder = DATA_DIR / "nse_quarterly"
OUTPUT_FOLDERS = {
    "W-FRI": weekly_folder,
    "ME": monthly_folder,
    "QE-DEC": quarterly_folder,
}
REPORT_FILE = DATA_DIR / "timeframe_build_report.csv"
REQUIRED = ("DATE", "OPEN", "HIGH", "LOW", "CLOSE")


def _backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    shutil.copy2(path, path.with_name(f"{path.name}.{stamp}.bak"))


def resample_safe(
    df: pd.DataFrame,
    rule: str,
    as_of_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Aggregate valid OHLCV bars and omit periods that have not closed yet."""
    data = df.copy()
    data.columns = [str(column).strip().upper() for column in data.columns]
    missing = set(REQUIRED).difference(data.columns)
    if missing:
        raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

    data["DATE"] = pd.to_datetime(data["DATE"], errors="coerce")
    for column in (*REQUIRED[1:], "VOLUME"):
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    valid_ohlc = data[list(REQUIRED[1:])].notna().all(axis=1)
    valid_ohlc &= (data[list(REQUIRED[1:])] > 0).all(axis=1)
    valid_ohlc &= (
        (data["HIGH"] >= data[["OPEN", "LOW", "CLOSE"]].max(axis=1))
        & (data["LOW"] <= data[["OPEN", "HIGH", "CLOSE"]].min(axis=1))
    )
    data = data.loc[data["DATE"].notna() & valid_ohlc].copy()
    if data.empty:
        return pd.DataFrame(columns=["DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "ISIN"])

    valid_isins = {
        clean_isin(value)
        for value in data["ISIN"].dropna()
        if validate_isin(value)
    } if "ISIN" in data.columns else set()
    if len(valid_isins) > 1:
        raise ValueError(f"conflicting valid ISINs in daily database: {', '.join(sorted(valid_isins))}")
    isin = next(iter(valid_isins), "UNKNOWN")

    data = data.sort_values("DATE").drop_duplicates(subset=["DATE"], keep="last")
    data = data.set_index("DATE")
    if "VOLUME" not in data:
        data["VOLUME"] = 0
    data["VOLUME"] = data["VOLUME"].fillna(0).clip(lower=0)
    aggregated = data.resample(rule).agg(
        {
            "OPEN": "first",
            "HIGH": "max",
            "LOW": "min",
            "CLOSE": "last",
            "VOLUME": "sum",
        }
    ).dropna(subset=["OPEN", "HIGH", "LOW", "CLOSE"])
    cutoff = pd.Timestamp(as_of_date or pd.Timestamp.now().normalize()).normalize()
    aggregated = aggregated.loc[aggregated.index.normalize() <= cutoff]
    aggregated = aggregated.reset_index()
    aggregated["ISIN"] = isin
    return aggregated


def main() -> None:
    if not daily_folder.is_dir():
        raise FileNotFoundError(f"Daily stock folder not found: {daily_folder}")
    for folder in OUTPUT_FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)
    _, bhavcopy_isins = scan_bhavcopy(DATA_DIR / "nse_bhavcopy")
    equity_isins = (
        load_isin_from_equity_master(DATA_DIR / "EQUITY_L.csv")
        if (DATA_DIR / "EQUITY_L.csv").is_file()
        else {}
    )

    report: list[dict[str, object]] = []
    skipped = 0
    files = sorted(path for path in daily_folder.glob("*.csv"))
    for index, path in enumerate(files, start=1):
        try:
            frame = pd.read_csv(path)
            frame.columns = [str(column).strip().upper() for column in frame.columns]
            missing = set(REQUIRED).difference(frame.columns)
            if missing:
                raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
            before = len(frame)
            daily = frame.copy()
            daily["DATE"] = pd.to_datetime(daily["DATE"], errors="coerce")
            for column in ("OPEN", "HIGH", "LOW", "CLOSE"):
                daily[column] = pd.to_numeric(daily[column], errors="coerce")
            valid = daily[list(REQUIRED)].notna().all(axis=1)
            valid &= (daily[["OPEN", "HIGH", "LOW", "CLOSE"]] > 0).all(axis=1)
            valid &= (
                (daily["HIGH"] >= daily[["OPEN", "LOW", "CLOSE"]].max(axis=1))
                & (daily["LOW"] <= daily[["OPEN", "HIGH", "CLOSE"]].min(axis=1))
            )
            invalid_count = int((~valid).sum())
            daily = daily.loc[valid].copy()
            if daily.empty:
                raise ValueError("no valid OHLC records")
            symbol = normalize_symbol(path.stem)
            existing_isins = {
                clean_isin(value)
                for value in daily.get("ISIN", pd.Series(dtype=object)).dropna()
                if validate_isin(value)
            }
            isin, _, _, _ = resolve_isin(
                symbol,
                {symbol: existing_isins},
                bhavcopy_isins,
                equity_isins,
            )
            if not existing_isins and isin != "UNKNOWN":
                daily["ISIN"] = isin
            for rule, folder in OUTPUT_FOLDERS.items():
                result = resample_safe(daily, rule)
                output = folder / path.name
                temporary = output.with_suffix(output.suffix + ".tmp")
                result.to_csv(temporary, index=False)
                if output.exists():
                    _backup(output)
                os.replace(temporary, output)
            report.append({
                "SYMBOL": path.stem.upper(),
                "STATUS": "PROCESSED",
                "DAILY_ROWS": before,
                "INVALID_OHLC_ROWS": invalid_count,
                "REASON": "",
            })
        except (
            OSError,
            UnicodeDecodeError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            ValueError,
        ) as error:
            skipped += 1
            report.append({
                "SYMBOL": path.stem.upper(),
                "STATUS": "SKIPPED",
                "DAILY_ROWS": 0,
                "INVALID_OHLC_ROWS": 0,
                "REASON": str(error),
            })
            print(f"Skipping {path.name}: {error}")
        if index % 500 == 0 or index == len(files):
            print(f"Processed {index:,}/{len(files):,} daily stock files")

    pd.DataFrame(report).to_csv(REPORT_FILE, index=False)
    print(f"Timeframe build report: {REPORT_FILE}")
    if skipped:
        print(f"Warning: {skipped} daily files were skipped; see {REPORT_FILE}")
    print(f"Built weekly, monthly, and quarterly timeframes for {len(files) - skipped:,} stocks.")


if __name__ == "__main__":
    main()
