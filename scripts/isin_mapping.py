from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


ELIGIBLE_SERIES = frozenset({"EQ"})
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

_COLUMN_ALIASES = {
    "SYMBOL": {"SYMBOL", "TCKRSYMB", "TRADINGSYMBOL"},
    "SERIES": {"SERIES", "SCTYSRS", "SECURITYSERIES"},
    "DATE": {"DATE", "DATE1", "TRADDT", "TRADINGDATE"},
    "OPEN": {"OPEN", "OPENPRICE", "OPNPRIC"},
    "HIGH": {"HIGH", "HIGHPRICE", "HGPRIC", "HGHPRIC"},
    "LOW": {"LOW", "LOWPRICE", "LWPRIC"},
    "CLOSE": {"CLOSE", "CLOSEPRICE", "CLSPRIC"},
    "VOLUME": {"VOLUME", "TTLTRDQNTY", "TTLTRADGVOL", "TOTALTRADEDVOLUME"},
    "ISIN": {"ISIN", "ISINNUMBER", "ISINID"},
}


def normalize_symbol(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    symbol = str(value).strip().upper()
    for suffix in (".NS", ".BO", "-EQ"):
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
            break
    return symbol.strip()


def clean_isin(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    isin = str(value).strip().upper()
    return "" if isin.casefold() in {"", "nan", "none", "unknown", "<na>"} else isin


def validate_isin(value: object) -> bool:
    isin = clean_isin(value)
    if not ISIN_PATTERN.fullmatch(isin):
        return False
    expanded = "".join(
        str(ord(char) - ord("A") + 10) if char.isalpha() else char
        for char in isin
    )
    checksum = 0
    for position, char in enumerate(reversed(expanded)):
        digit = int(char)
        if position % 2:
            digit *= 2
            digit = digit // 10 + digit % 10
        checksum += digit
    return checksum % 10 == 0


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        re.sub(r"[^A-Z0-9]", "", alias): canonical
        for canonical, names in _COLUMN_ALIASES.items()
        for alias in names
    }
    rename = {}
    for column in frame.columns:
        key = re.sub(r"[^A-Z0-9]", "", str(column).strip().upper())
        if key in aliases:
            rename[column] = aliases[key]
    return frame.rename(columns=rename)


def load_isin_from_stock_database(path: str | Path) -> set[str]:
    try:
        frame = pd.read_csv(path, usecols=lambda name: str(name).strip().upper() == "ISIN")
    except ValueError:
        return set()
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return set()
    if frame.empty:
        return set()
    values = frame.iloc[:, 0].map(clean_isin)
    return {value for value in values if validate_isin(value)}


def _read_bhavcopy(path: Path) -> pd.DataFrame | None:
    try:
        return normalize_columns(pd.read_csv(path))
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None


def scan_bhavcopy(
    folder: str | Path,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return all symbol/series observations and valid ISIN candidates by symbol."""
    series_by_symbol: dict[str, set[str]] = defaultdict(set)
    isins_by_symbol: dict[str, set[str]] = defaultdict(set)
    root = Path(folder)
    if not root.is_dir():
        return {}, {}
    for path in sorted(root.glob("*.csv")):
        frame = _read_bhavcopy(path)
        if frame is None or "SYMBOL" not in frame or "SERIES" not in frame:
            continue
        has_isin = "ISIN" in frame
        columns = ["SYMBOL", "SERIES"] + (["ISIN"] if has_isin else [])
        for row in frame[columns].itertuples(index=False, name=None):
            symbol = normalize_symbol(row[0])
            series = str(row[1]).strip().upper()
            if not symbol or not series:
                continue
            series_by_symbol[symbol].add(series)
            if has_isin:
                isin = clean_isin(row[2])
                if validate_isin(isin):
                    isins_by_symbol[symbol].add(isin)
    return dict(series_by_symbol), dict(isins_by_symbol)


def load_isin_from_bhavcopy(folder: str | Path) -> dict[str, set[str]]:
    return scan_bhavcopy(folder)[1]


def load_isin_from_equity_master(path: str | Path) -> dict[str, set[str]]:
    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return {}
    columns = {str(column).strip().upper(): column for column in frame.columns}
    symbol_column = columns.get("SYMBOL")
    isin_column = next(
        (column for key, column in columns.items() if "ISIN" in key),
        None,
    )
    if symbol_column is None or isin_column is None:
        raise ValueError(f"Equity master must contain SYMBOL and ISIN columns: {path}")
    result: dict[str, set[str]] = defaultdict(set)
    for symbol, raw_isin in zip(frame[symbol_column], frame[isin_column]):
        key = normalize_symbol(symbol)
        isin = clean_isin(raw_isin)
        if key and validate_isin(isin):
            result[key].add(isin)
    return dict(result)


def _candidate_values(mapping: Mapping[str, object] | None, symbol: str) -> set[str]:
    if not mapping:
        return set()
    value = mapping.get(symbol, set())
    values: Iterable[object] = value if isinstance(value, (set, list, tuple)) else (value,)
    return {clean_isin(item) for item in values if validate_isin(item)}


def resolve_isin(
    symbol: str,
    stock_isins: Mapping[str, object] | None = None,
    bhavcopy_isins: Mapping[str, object] | None = None,
    equity_isins: Mapping[str, object] | None = None,
) -> tuple[str, str, str, list[dict[str, str]]]:
    """Resolve by source priority without choosing arbitrarily within conflicts."""
    key = normalize_symbol(symbol)
    candidates = (
        ("stock_database", stock_isins),
        ("bhavcopy", bhavcopy_isins),
        ("equity_master", equity_isins),
    )
    selected, source = "", "UNKNOWN"
    conflicts: list[dict[str, str]] = []
    for name, mapping in candidates:
        values = _candidate_values(mapping, key)
        if len(values) > 1:
            conflicts.extend(
                {"SYMBOL": key, "ISIN": value, "SOURCE": name, "REASON": "multiple valid ISINs for symbol"}
                for value in sorted(values)
            )
            continue
        if values:
            selected, source = next(iter(values)), name
            break
    status = "VALID" if selected else "UNKNOWN"
    if selected:
        for name, mapping in candidates:
            if name == source:
                continue
            for value in sorted(_candidate_values(mapping, key)):
                if value != selected:
                    conflicts.append(
                        {
                            "SYMBOL": key,
                            "ISIN": value,
                            "SOURCE": name,
                            "REASON": f"conflicts with higher-priority {source} value {selected}",
                        }
                    )
        if conflicts:
            status = "VALID_WITH_CONFLICT"
    return selected or "UNKNOWN", source, status, conflicts


def validate_symbol_isin_mapping(
    mapping: Mapping[str, object],
) -> list[dict[str, str]]:
    symbols_by_isin: dict[str, set[str]] = defaultdict(set)
    for raw_symbol, raw_isin in mapping.items():
        symbol = normalize_symbol(raw_symbol)
        for isin in _candidate_values({symbol: raw_isin}, symbol):
            symbols_by_isin[isin].add(symbol)
    return [
        {
            "SYMBOL": symbol,
            "ISIN": isin,
            "SOURCE": "resolved_mapping",
            "REASON": f"ISIN is associated with multiple symbols: {', '.join(sorted(symbols))}",
        }
        for isin, symbols in sorted(symbols_by_isin.items())
        if len(symbols) > 1
        for symbol in sorted(symbols)
    ]
