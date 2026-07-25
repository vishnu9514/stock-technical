import argparse
import os
from typing import Dict, Optional

import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

DAILY_FOLDER = os.path.join(DATA_DIR, "nse_stocks")
WEEKLY_FOLDER = os.path.join(DATA_DIR, "nse_weekly")
MONTHLY_FOLDER = os.path.join(DATA_DIR, "nse_monthly")
ISIN_FILE = os.path.join(DATA_DIR, "EQUITY_L.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "stochrsi_strict_dashboard.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a strict StochRSI M->W->D hierarchy dashboard."
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        default=None,
        help="As-of date in YYYY-MM-DD format. Default: latest available daily date.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=30.0,
        help="Threshold for K and D eligibility checks. Default: 30.",
    )
    parser.add_argument(
        "--include-stale",
        action="store_true",
        help="Include symbols with older snapshot dates instead of only the current reference dates.",
    )
    return parser.parse_args()


def normalize_symbol(value: str) -> str:
    symbol = str(value).upper().strip()
    for suffix in ("-EQ", ".NS"):
        if symbol.endswith(suffix):
            symbol = symbol[: -len(suffix)]
    return symbol


def load_isin_map() -> Dict[str, str]:
    if not os.path.exists(ISIN_FILE):
        return {}

    isin_df = pd.read_csv(ISIN_FILE)
    isin_df.columns = isin_df.columns.str.upper().str.strip()

    symbol_col = next((column for column in isin_df.columns if "SYMBOL" in column), None)
    isin_col = next((column for column in isin_df.columns if "ISIN" in column), None)

    if symbol_col is None or isin_col is None:
        return {}

    isin_df["SYMBOL_KEY"] = isin_df[symbol_col].astype(str).map(normalize_symbol)
    isin_df["ISIN_VALUE"] = isin_df[isin_col].astype(str).str.strip()

    return (
        isin_df.dropna(subset=["SYMBOL_KEY"])
        .drop_duplicates(subset=["SYMBOL_KEY"])
        .set_index("SYMBOL_KEY")["ISIN_VALUE"]
        .to_dict()
    )


def parse_cutoff_date(as_of_date: Optional[str]) -> Optional[pd.Timestamp]:
    if not as_of_date:
        return None

    parsed = pd.to_datetime(as_of_date, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid --as-of-date value: {as_of_date}")
    return pd.Timestamp(parsed).normalize()


def detect_reference_date(folder: str, cutoff_date: Optional[pd.Timestamp]) -> Optional[pd.Timestamp]:
    latest_dates = []

    for file in os.listdir(folder):
        if not file.lower().endswith(".csv"):
            continue

        path = os.path.join(folder, file)
        try:
            df = pd.read_csv(path, usecols=["DATE", "K", "D"])
        except Exception:
            continue

        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
        df["K"] = pd.to_numeric(df["K"], errors="coerce")
        df["D"] = pd.to_numeric(df["D"], errors="coerce")

        valid = df.dropna(subset=["DATE", "K", "D"])
        if cutoff_date is not None:
            valid = valid[valid["DATE"] <= cutoff_date]

        if valid.empty:
            continue

        latest_dates.append(valid["DATE"].max())

    if not latest_dates:
        return None

    return pd.Series(latest_dates).max()


def load_snapshot(folder: str, filename: str, cutoff_date: Optional[pd.Timestamp]) -> Optional[Dict[str, object]]:
    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        return None

    try:
        df = pd.read_csv(path)
    except Exception:
        return None

    required_columns = {"DATE", "CLOSE", "K", "D"}
    if not required_columns.issubset(df.columns):
        return None

    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    for column in ["CLOSE", "RSI", "K", "D"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    valid = (
        df.dropna(subset=["DATE", "K", "D"])
        .sort_values("DATE")
        .reset_index(drop=True)
    )

    if cutoff_date is not None:
        valid = valid[valid["DATE"] <= cutoff_date].reset_index(drop=True)

    if valid.empty:
        return None

    snapshot_index = len(valid) - 1
    if snapshot_index < 0:
        return None

    row = valid.iloc[snapshot_index]
    return {
        "DATE": row["DATE"],
        "CLOSE": row["CLOSE"],
        "RSI": row["RSI"] if "RSI" in row.index else pd.NA,
        "K": row["K"],
        "D": row["D"],
    }


def is_below_threshold(snapshot: Dict[str, object], threshold: float) -> bool:
    return bool(snapshot["K"] < threshold and snapshot["D"] < threshold)


def format_number(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    return round(float(value), 2)


def status_label(monthly_ok: bool, weekly_ok: bool, daily_ok: bool) -> str:
    if daily_ok:
        return "DAILY_BELOW_30"
    if weekly_ok:
        return "DAILY_ELIGIBLE"
    if monthly_ok:
        return "WEEKLY_ELIGIBLE"
    return "NOT_ELIGIBLE"


def main() -> None:
    args = parse_args()
    threshold = float(args.threshold)
    cutoff_date = parse_cutoff_date(args.as_of_date)

    if cutoff_date is None:
        cutoff_date = detect_reference_date(DAILY_FOLDER, None)
        if cutoff_date is None:
            raise ValueError("Could not detect a latest daily reference date from data.")

    reference_dates = {
        "M": detect_reference_date(MONTHLY_FOLDER, cutoff_date),
        "W": detect_reference_date(WEEKLY_FOLDER, cutoff_date),
        "D": detect_reference_date(DAILY_FOLDER, cutoff_date),
    }

    if any(value is None for value in reference_dates.values()):
        raise ValueError("Could not detect reference dates for monthly/weekly/daily data.")

    isin_map = load_isin_map()
    stock_files = sorted(
        file for file in os.listdir(DAILY_FOLDER) if file.lower().endswith(".csv")
    )

    results = []
    print(
        f"Building strict StochRSI hierarchy dashboard for {len(stock_files):,} stocks "
        f"with threshold {threshold:.2f}"
    )
    print(
        "As-of date:",
        cutoff_date.date(),
        "| Reference dates:",
        f"M={reference_dates['M'].date()}",
        f"W={reference_dates['W'].date()}",
        f"D={reference_dates['D'].date()}",
    )

    for index, file in enumerate(stock_files, start=1):
        symbol = normalize_symbol(os.path.splitext(file)[0])

        monthly = load_snapshot(MONTHLY_FOLDER, file, cutoff_date)
        weekly = load_snapshot(WEEKLY_FOLDER, file, cutoff_date)
        daily = load_snapshot(DAILY_FOLDER, file, cutoff_date)

        if monthly is None or weekly is None or daily is None:
            continue

        if not args.include_stale:
            if monthly["DATE"] != reference_dates["M"]:
                continue
            if weekly["DATE"] != reference_dates["W"]:
                continue
            if daily["DATE"] != reference_dates["D"]:
                continue

        monthly_ok = is_below_threshold(monthly, threshold)
        if not monthly_ok:
            continue

        weekly_eligible = monthly_ok
        weekly_ok = weekly_eligible and is_below_threshold(weekly, threshold)
        daily_eligible = weekly_ok
        daily_ok = daily_eligible and is_below_threshold(daily, threshold)

        results.append(
            {
                "AS_OF_DATE": cutoff_date.date().isoformat(),
                "STOCK": symbol,
                "ISIN": isin_map.get(symbol, "UNKNOWN"),
                "M_DATE": monthly["DATE"],
                "M_RSI": format_number(monthly["RSI"]),
                "M_K": format_number(monthly["K"]),
                "M_D": format_number(monthly["D"]),
                "MONTHLY_BELOW_30": monthly_ok,
                "WEEKLY_ELIGIBLE": weekly_eligible,
                "W_DATE": weekly["DATE"],
                "W_RSI": format_number(weekly["RSI"]),
                "W_K": format_number(weekly["K"]),
                "W_D": format_number(weekly["D"]),
                "WEEKLY_BELOW_30": weekly_ok,
                "DAILY_ELIGIBLE": daily_eligible,
                "D_DATE": daily["DATE"],
                "D_RSI": format_number(daily["RSI"]),
                "D_K": format_number(daily["K"]),
                "D_D": format_number(daily["D"]),
                "DAILY_BELOW_30": daily_ok,
                "STATUS": status_label(monthly_ok, weekly_ok, daily_ok),
            }
        )

        if index % 500 == 0 or index == len(stock_files):
            print(f"Processed {index:,}/{len(stock_files):,} stocks")

    dashboard = pd.DataFrame(results)

    if not dashboard.empty:
        dashboard["WEEKLY_PRIORITY"] = dashboard["WEEKLY_BELOW_30"].astype(int) * -1
        dashboard["DAILY_PRIORITY"] = dashboard["DAILY_BELOW_30"].astype(int) * -1
        dashboard = dashboard.sort_values(
            ["DAILY_PRIORITY", "WEEKLY_PRIORITY", "M_K", "W_K", "D_K", "STOCK"],
            ascending=[True, True, True, True, True, True],
        ).drop(columns=["WEEKLY_PRIORITY", "DAILY_PRIORITY"])

    dashboard.to_csv(OUTPUT_FILE, index=False)

    print("\nStrict StochRSI dashboard generated")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Rows: {len(dashboard):,}")


if __name__ == "__main__":
    main()
