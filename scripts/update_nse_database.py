from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.isin_mapping import (  # noqa: E402
    ELIGIBLE_SERIES,
    clean_isin,
    load_isin_from_equity_master,
    normalize_columns,
    normalize_symbol,
    resolve_isin,
    validate_isin,
)

BHAVCOPY_FOLDER = BASE_DIR / "data" / "nse_bhavcopy"
STOCK_FOLDER = BASE_DIR / "data" / "nse_stocks"
EQUITY_FILE = BASE_DIR / "data" / "EQUITY_L.csv"
AUDIT_FILE = BASE_DIR / "data" / "update_nse_database_audit.csv"
REQUIRED_COLUMNS = {"SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"}
PRICE_COLUMNS = ("OPEN", "HIGH", "LOW", "CLOSE")


def _file_date(filename: str) -> pd.Timestamp | None:
    match = re.search(r"(\d{8})(?=\.csv$)", filename, re.IGNORECASE)
    if not match:
        return None
    try:
        return pd.Timestamp(datetime.strptime(match.group(1), "%d%m%Y").date())
    except ValueError:
        return None


def _parse_date(value: object) -> pd.Timestamp:
    if value is None or pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    for date_format in ("%Y-%m-%d", "%Y%m%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return pd.Timestamp(datetime.strptime(text, date_format))
        except ValueError:
            continue
    return pd.to_datetime(text, errors="coerce", dayfirst=True)


def _read_bhavcopy(path: Path) -> pd.DataFrame | None:
    try:
        frame = normalize_columns(pd.read_csv(path))
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        print(f"Could not read Bhavcopy {path}: {error}")
        return None
    if not REQUIRED_COLUMNS.issubset(frame.columns):
        missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
        print(f"Skipping Bhavcopy {path}; missing columns: {', '.join(missing)}")
        return None
    if "DATE" not in frame:
        frame["DATE"] = _file_date(path.name)
    else:
        parsed = frame["DATE"].map(_parse_date)
        fallback_date = _file_date(path.name)
        frame["DATE"] = parsed.fillna(fallback_date) if fallback_date is not None else parsed
    return frame


def _valid_market_rows(frame: pd.DataFrame, path: Path) -> tuple[pd.DataFrame, int]:
    frame = frame.copy()
    frame["SYMBOL"] = frame["SYMBOL"].map(normalize_symbol)
    frame["SERIES"] = frame["SERIES"].astype(str).str.strip().str.upper()
    frame["DATE"] = pd.to_datetime(frame["DATE"], errors="coerce")
    for column in (*PRICE_COLUMNS, "VOLUME"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    valid = (
        frame["SYMBOL"].ne("")
        & frame["SERIES"].isin(ELIGIBLE_SERIES)
        & frame["DATE"].notna()
        & frame[list(PRICE_COLUMNS)].notna().all(axis=1)
        & (frame[list(PRICE_COLUMNS)] > 0).all(axis=1)
        & frame["VOLUME"].notna()
        & (frame["VOLUME"] >= 0)
        & (frame["HIGH"] >= frame["LOW"])
        & (frame["HIGH"] >= frame["OPEN"])
        & (frame["HIGH"] >= frame["CLOSE"])
        & (frame["LOW"] <= frame["OPEN"])
        & (frame["LOW"] <= frame["CLOSE"])
    )
    invalid_count = int((~valid).sum())
    if invalid_count:
        print(f"Skipping {invalid_count} invalid EQ OHLC/volume rows in {path.name}")
    return frame.loc[valid, ["SYMBOL", "DATE", *PRICE_COLUMNS, "VOLUME"] + (["ISIN"] if "ISIN" in frame else [])], invalid_count


def load_bhavcopy_records(
    folder: str | Path = BHAVCOPY_FOLDER,
) -> tuple[dict[str, list[dict]], dict[str, set[str]], list[dict[str, object]]]:
    root = Path(folder)
    if not root.is_dir():
        raise FileNotFoundError(f"Bhavcopy folder not found: {root}")
    files = sorted(root.glob("*.csv"))
    if not files:
        raise RuntimeError(f"No Bhavcopy CSV files found in {root}")

    records: dict[str, list[dict]] = {}
    bhavcopy_isins: dict[str, set[str]] = {}
    audit: list[dict[str, object]] = []
    print(f"Reading {len(files):,} historical Bhavcopy files...")
    for index, path in enumerate(files, start=1):
        frame = _read_bhavcopy(path)
        if frame is None:
            audit.append({"FILE": path.name, "STATUS": "SKIPPED", "REASON": "unreadable or unsupported columns"})
            continue
        valid, invalid_count = _valid_market_rows(frame, path)
        for row in valid.itertuples(index=False, name=None):
            symbol, date, open_price, high_price, low_price, close_price, volume, *rest = row
            isin = clean_isin(rest[0]) if rest else ""
            if validate_isin(isin):
                bhavcopy_isins.setdefault(symbol, set()).add(isin)
            records.setdefault(symbol, []).append(
                {
                    "DATE": date,
                    "OPEN": open_price,
                    "HIGH": high_price,
                    "LOW": low_price,
                    "CLOSE": close_price,
                    "VOLUME": volume,
                    "ISIN": isin if validate_isin(isin) else "",
                }
            )
        audit.append({
            "FILE": path.name,
            "STATUS": "PROCESSED" if not valid.empty else "NO_ELIGIBLE_ROWS",
            "VALID_EQ_ROWS": len(valid),
            "INVALID_ROWS": invalid_count,
            "REASON": "",
        })
        if index % 250 == 0 or index == len(files):
            print(f"Loaded {index:,}/{len(files):,} Bhavcopy files")
    return records, bhavcopy_isins, audit


def _stock_database_isins(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        frame = pd.read_csv(path, usecols=lambda name: str(name).strip().upper() == "ISIN")
    except ValueError:
        return set()
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        print(f"Could not read existing stock ISINs from {path}: {error}")
        return set()
    if frame.empty:
        return set()
    return {
        value for value in frame.iloc[:, 0].map(clean_isin)
        if validate_isin(value)
    }


def _backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    backup_path = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup_path)


def _update_stock_file(
    path: Path,
    records: list[dict],
    bhavcopy_isins: dict[str, set[str]],
    equity_isins: dict[str, set[str]],
) -> tuple[bool, int, str]:
    symbol = normalize_symbol(path.stem)
    if path.exists():
        try:
            existing = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            existing = pd.DataFrame(columns=["DATE", *PRICE_COLUMNS, "VOLUME", "ISIN"])
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
            return False, 0, f"unreadable existing file: {error}"
        existing.columns = [str(column).strip().upper() for column in existing.columns]
    else:
        existing = pd.DataFrame(columns=["DATE", *PRICE_COLUMNS, "VOLUME", "ISIN"])

    if not existing.empty and "DATE" not in existing.columns:
        return False, 0, "missing DATE column"
    if not existing.empty:
        existing["DATE"] = pd.to_datetime(existing["DATE"], errors="coerce")
    existing_original_count = len(existing)
    original_existing_dates = (
        existing["DATE"].tolist() if "DATE" in existing.columns else []
    )
    existing = existing.dropna(subset=["DATE"]) if "DATE" in existing.columns else existing
    existing_isins = _stock_database_isins(path)
    record_isins = {
        clean_isin(record.get("ISIN"))
        for record in records
        if validate_isin(record.get("ISIN"))
    }
    bhavcopy_isins = {
        key: set(values) for key, values in bhavcopy_isins.items()
    }
    if record_isins:
        bhavcopy_isins.setdefault(symbol, set()).update(record_isins)
    had_isin_column = "ISIN" in existing.columns
    old_isin_values = (
        existing["ISIN"].map(clean_isin).tolist()
        if had_isin_column
        else []
    )
    resolved, _, status, _ = resolve_isin(
        symbol,
        {symbol: existing_isins},
        bhavcopy_isins,
        equity_isins,
    )
    existing_dates = set(existing["DATE"]) if "DATE" in existing else set()
    incoming = pd.DataFrame(records)
    if not incoming.empty:
        incoming["DATE"] = pd.to_datetime(incoming["DATE"], errors="coerce")
        incoming = incoming.dropna(subset=["DATE"])
        incoming = incoming.loc[~incoming["DATE"].isin(existing_dates)]
    added = len(incoming)
    if not incoming.empty:
        if "ISIN" not in incoming:
            incoming["ISIN"] = ""
        incoming["ISIN"] = incoming["ISIN"].map(
            lambda value: clean_isin(value) if validate_isin(value) else ""
        )
        if resolved != "UNKNOWN":
            incoming["ISIN"] = resolved
        else:
            incoming["ISIN"] = incoming["ISIN"].replace("", "UNKNOWN")
        existing = pd.concat([existing, incoming], ignore_index=True, sort=False)

    if existing.empty and not records:
        return True, 0, "no data"
    if "ISIN" not in existing:
        existing["ISIN"] = resolved
    else:
        existing_isin_values = existing["ISIN"].map(clean_isin)
        good = existing_isin_values.map(validate_isin)
        if resolved != "UNKNOWN":
            existing.loc[~good, "ISIN"] = resolved
        else:
            existing.loc[~good, "ISIN"] = "UNKNOWN"
    if "DATE" in existing:
        existing = existing.dropna(subset=["DATE"])
        existing = existing.drop_duplicates(subset=["DATE"], keep="first")
        existing = existing.sort_values("DATE")

    final_dates = existing["DATE"].tolist() if "DATE" in existing.columns else []
    changed = (
        added > 0
        or len(final_dates) != existing_original_count
        or final_dates != sorted(set(original_existing_dates))
    )
    if path.exists() and not changed:
        changed = not had_isin_column or (
            resolved != "UNKNOWN"
            and any(not validate_isin(value) for value in old_isin_values)
        )
    if changed:
        if path.exists():
            _backup(path)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        existing.to_csv(temp_path, index=False)
        os.replace(temp_path, path)
    elif not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        existing.to_csv(path, index=False)
    return True, added, status


def update_stock_file(
    file: str | Path,
    records: list[dict],
    bhavcopy_isins: dict[str, set[str]] | str | None = None,
    equity_isins: dict[str, set[str]] | None = None,
) -> tuple[bool, int]:
    """Compatibility wrapper retaining the original two-value update result."""
    path = Path(file)
    if not path.is_absolute():
        path = Path(STOCK_FOLDER) / path
    symbol = normalize_symbol(path.stem)
    bhavcopy_mapping = (
        bhavcopy_isins if isinstance(bhavcopy_isins, dict) else {}
    )
    equity_mapping = dict(equity_isins or {})
    if isinstance(bhavcopy_isins, str) and validate_isin(bhavcopy_isins):
        equity_mapping.setdefault(symbol, set()).add(clean_isin(bhavcopy_isins))
    success, added, _ = _update_stock_file(
        path,
        records,
        bhavcopy_mapping,
        equity_mapping,
    )
    return success, added


def main() -> None:
    STOCK_FOLDER.mkdir(parents=True, exist_ok=True)
    records, bhavcopy_isins, audit = load_bhavcopy_records()
    equity_isins = load_isin_from_equity_master(EQUITY_FILE)
    symbols = sorted(set(records) | {path.stem.upper() for path in STOCK_FOLDER.glob("*.csv")})
    updated = added = skipped = 0
    for index, symbol in enumerate(symbols, start=1):
        path = STOCK_FOLDER / f"{symbol}.csv"
        success, new_rows, status = _update_stock_file(
            path,
            records.get(symbol, []),
            bhavcopy_isins,
            equity_isins,
        )
        updated += int(success)
        added += new_rows
        if not success:
            skipped += 1
            audit.append({"SYMBOL": symbol, "STATUS": "SKIPPED", "REASON": status})
        if index % 250 == 0 or index == len(symbols):
            print(f"Processed {index:,}/{len(symbols):,} eligible stock files")
    pd.DataFrame(audit).to_csv(AUDIT_FILE, index=False)
    print(f"\nNSE database update completed: {updated:,} updated, {added:,} new rows, {skipped:,} skipped")
    print(f"Update audit: {AUDIT_FILE}")
    if skipped:
        raise RuntimeError(f"{skipped} stock files were skipped; see {AUDIT_FILE}")


if __name__ == "__main__":
    main()
