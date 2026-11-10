from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
FOLDERS = {
    "D": DATA_DIR / "nse_stocks",
    "W": DATA_DIR / "nse_weekly",
    "M": DATA_DIR / "nse_monthly",
    "3M": DATA_DIR / "nse_quarterly",
}
REPORT_FILE = DATA_DIR / "macd_calculation_report.csv"
INDICATOR_COLUMNS = ("EMA12", "EMA26", "MACD", "MACD_SIGNAL", "MACD_HIST")
PARAMETERS = {"fast_ema": 12, "slow_ema": 26, "signal_ema": 9}


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate standard MACD 12/26/9 on chronologically ordered CLOSE prices."""
    result = df.copy()
    close = pd.to_numeric(result["CLOSE"], errors="coerce")
    result["EMA12"] = close.ewm(span=12, adjust=False).mean()
    result["EMA26"] = close.ewm(span=26, adjust=False).mean()
    result["MACD"] = result["EMA12"] - result["EMA26"]
    result["MACD_SIGNAL"] = result["MACD"].ewm(span=9, adjust=False).mean()
    result["MACD_HIST"] = result["MACD"] - result["MACD_SIGNAL"]
    return result


def _same_values(existing: pd.DataFrame, calculated: pd.DataFrame) -> bool:
    if not set(INDICATOR_COLUMNS).issubset(existing.columns):
        return False
    for column in INDICATOR_COLUMNS:
        old = pd.to_numeric(existing[column], errors="coerce").to_numpy(dtype=float)
        new = pd.to_numeric(calculated[column], errors="coerce").to_numpy(dtype=float)
        if old.shape != new.shape or not np.allclose(old, new, rtol=1e-12, atol=1e-12, equal_nan=True):
            return False
    return True


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def main() -> None:
    report: list[dict[str, object]] = []
    for timeframe, folder in FOLDERS.items():
        if not folder.is_dir():
            raise FileNotFoundError(f"Required timeframe folder not found: {folder}")
        files = sorted(folder.glob("*.csv"))
        print(f"Processing {timeframe}: {len(files):,} files")
        for index, path in enumerate(files, start=1):
            try:
                original = pd.read_csv(path)
                frame = original.copy()
                frame.columns = [str(column).strip().upper() for column in frame.columns]
                if "DATE" not in frame or "CLOSE" not in frame:
                    report.append({
                        "TIMEFRAME": timeframe,
                        "SYMBOL": path.stem.upper(),
                        "STATUS": "SKIPPED",
                        "REASON": "missing DATE or CLOSE column",
                    })
                    continue
                frame["DATE"] = pd.to_datetime(frame["DATE"], errors="coerce")
                frame["CLOSE"] = pd.to_numeric(frame["CLOSE"], errors="coerce")
                frame = frame.dropna(subset=["DATE", "CLOSE"])
                if frame.empty:
                    report.append({
                        "TIMEFRAME": timeframe,
                        "SYMBOL": path.stem.upper(),
                        "STATUS": "SKIPPED",
                        "REASON": "no valid dated CLOSE records",
                    })
                    continue
                original_indicators = frame.copy()
                original_dates = frame["DATE"].tolist()
                frame = frame.sort_values("DATE").drop_duplicates(subset=["DATE"], keep="last")
                calculated = add_macd(frame)
                unchanged_order = original_dates == frame["DATE"].tolist()
                same_indicators = unchanged_order and _same_values(original_indicators, calculated)
                if not same_indicators:
                    _backup(path)
                    calculated.to_csv(path, index=False)
                report.append({
                    "TIMEFRAME": timeframe,
                    "SYMBOL": path.stem.upper(),
                    "STATUS": "UPDATED" if not same_indicators else "CURRENT",
                    "REASON": "",
                })
            except (
                OSError,
                UnicodeDecodeError,
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
                KeyError,
                ValueError,
            ) as error:
                report.append({
                    "TIMEFRAME": timeframe,
                    "SYMBOL": path.stem.upper(),
                    "STATUS": "SKIPPED",
                    "REASON": str(error),
                })
                print(f"Skipping {timeframe}/{path.name}: {error}")
            if index % 500 == 0 or index == len(files):
                print(f"{timeframe}: processed {index:,}/{len(files):,}")
    report_frame = pd.DataFrame(report, columns=["TIMEFRAME", "SYMBOL", "STATUS", "REASON"])
    report_frame.to_csv(REPORT_FILE, index=False)
    print(f"MACD calculation report: {REPORT_FILE}")
    skipped = report_frame.loc[report_frame["STATUS"] == "SKIPPED"]
    if not skipped.empty:
        print(f"Skipped {len(skipped):,} inputs; see {REPORT_FILE}")
    print(f"MACD calculated with EMA12/EMA26/signal9 for D/W/M/3M.")


if __name__ == "__main__":
    main()
