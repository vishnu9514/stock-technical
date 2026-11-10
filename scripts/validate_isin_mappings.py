from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.isin_mapping import (  # noqa: E402
    ELIGIBLE_SERIES,
    clean_isin,
    load_isin_from_equity_master,
    load_isin_from_stock_database,
    normalize_symbol,
    resolve_isin,
    scan_bhavcopy,
    validate_isin,
    validate_symbol_isin_mapping,
)

DATA_DIR = BASE_DIR / "data"
EQUITY_FILE = DATA_DIR / "EQUITY_L.csv"
BHAVCOPY_FOLDER = DATA_DIR / "nse_bhavcopy"
TIMEFRAME_FOLDERS = {
    "D": DATA_DIR / "nse_stocks",
    "W": DATA_DIR / "nse_weekly",
    "M": DATA_DIR / "nse_monthly",
    "3M": DATA_DIR / "nse_quarterly",
}
MAPPING_REPORT = DATA_DIR / "isin_mapping_report.csv"
CONFLICT_REPORT = DATA_DIR / "isin_conflicts.csv"


def main() -> None:
    for folder in TIMEFRAME_FOLDERS.values():
        if not folder.is_dir():
            raise FileNotFoundError(f"Required stock folder not found: {folder}")
    series_by_symbol, bhavcopy_isins = scan_bhavcopy(BHAVCOPY_FOLDER)
    equity_isins = load_isin_from_equity_master(EQUITY_FILE) if EQUITY_FILE.is_file() else {}
    symbol_sets = {
        key: {normalize_symbol(path.stem) for path in folder.glob("*.csv")}
        for key, folder in TIMEFRAME_FOLDERS.items()
    }
    eligible = set().union(
        symbol_sets["D"],
        {
            symbol for symbol, series in series_by_symbol.items()
            if series.intersection(ELIGIBLE_SERIES)
        },
    )
    mappings = []
    conflicts: list[dict[str, str]] = []
    for index, symbol in enumerate(sorted(eligible), start=1):
        stock_isins: set[str] = set()
        invalid_values = 0
        for folder in TIMEFRAME_FOLDERS.values():
            path = folder / f"{symbol}.csv"
            candidates = load_isin_from_stock_database(path) if path.is_file() else set()
            stock_isins.update(candidates)
            if path.is_file() and path.stat().st_size:
                try:
                    frame = pd.read_csv(path, usecols=lambda name: str(name).strip().upper() == "ISIN")
                    if not frame.empty:
                        invalid_values += sum(
                            bool(clean_isin(value)) and not validate_isin(value)
                            for value in frame.iloc[:, 0]
                        )
                except ValueError:
                    pass
        isin, source, status, found_conflicts = resolve_isin(
            symbol,
            {symbol: stock_isins},
            bhavcopy_isins,
            equity_isins,
        )
        conflicts.extend(found_conflicts)
        if invalid_values:
            conflicts.append({
                "SYMBOL": symbol,
                "ISIN": "",
                "SOURCE": "stock_database",
                "REASON": f"{invalid_values} malformed or invalid ISIN values",
            })
        mappings.append({
            "SYMBOL": symbol,
            "ISIN": isin,
            "ISIN_SOURCE": source,
            "ISIN_STATUS": status if not invalid_values else f"{status}_INVALID_SOURCE_VALUES",
        })
        if index % 500 == 0 or index == len(eligible):
            print(f"Validated {index:,}/{len(eligible):,} symbols")

    conflicts.extend(validate_symbol_isin_mapping({
        row["SYMBOL"]: row["ISIN"]
        for row in mappings
        if row["ISIN"] != "UNKNOWN"
    }))
    pd.DataFrame(
        mappings,
        columns=["SYMBOL", "ISIN", "ISIN_SOURCE", "ISIN_STATUS"],
    ).to_csv(MAPPING_REPORT, index=False)
    pd.DataFrame(
        conflicts,
        columns=["SYMBOL", "ISIN", "SOURCE", "REASON"],
    ).drop_duplicates().to_csv(CONFLICT_REPORT, index=False)

    expected = "INE144J01027"
    reference = next((row for row in mappings if row["SYMBOL"] == "20MICRONS"), None)
    if reference is None or reference["ISIN"] != expected:
        raise RuntimeError(
            f"20MICRONS ISIN validation failed; expected {expected}, "
            f"found {reference['ISIN'] if reference else 'no mapping'}"
        )
    print(
        f"ISIN mapping complete: {len(mappings):,} symbols; "
        f"{sum(row['ISIN'] != 'UNKNOWN' for row in mappings):,} resolved; "
        f"{len(conflicts):,} conflict/quality records."
    )
    print(f"Mapping report: {MAPPING_REPORT}")
    print(f"Conflict report: {CONFLICT_REPORT}")


if __name__ == "__main__":
    main()
