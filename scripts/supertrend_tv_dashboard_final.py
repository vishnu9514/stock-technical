import argparse
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

DAILY_FOLDER = os.path.join(DATA_DIR, "nse_stocks")
WEEKLY_FOLDER = os.path.join(DATA_DIR, "nse_weekly")
MONTHLY_FOLDER = os.path.join(DATA_DIR, "nse_monthly")

ISIN_FILE = os.path.join(DATA_DIR, "EQUITY_L.csv")
INDUSTRY_FILE = os.path.join(DATA_DIR, "industry_with_sector.csv")
MAIN_INDUSTRY_FILE = os.path.join(DATA_DIR, "main industries.xlsx")

DASHBOARD_OUTPUT = os.path.join(DATA_DIR, "supertrend_tv_dashboard.csv")
SIGNALS_OUTPUT = os.path.join(DATA_DIR, "supertrend_tv_mwd_signals.csv")
STOCHRSI_RECENT_OUTPUT = os.path.join(DATA_DIR, "stochrsi_recent_dashboard.csv")
STOCHRSI_DAILY_ELIGIBLE_OUTPUT = os.path.join(DATA_DIR, "stochrsi_recent_daily_eligible.csv")
STOCHRSI_DAILY_BELOW_30_OUTPUT = os.path.join(DATA_DIR, "stochrsi_recent_daily_below_30.csv")

PIPELINE_SCRIPTS = [
    "scripts/update_nse_bhavcopy.py",
    "scripts/update_nse_database.py",
    "scripts/update_nse_with_volume_final.py",
    "scripts/build_timeframes_fixed.py",
    "scripts/calculate_stochrsi_all_timeframes.py",
    "scripts/add_main_industry_all_timeframes.py",
]

TIMEFRAME_CONFIG = {
    "D": {"folder": DAILY_FOLDER, "use_closed_bar": False},
    "W": {"folder": WEEKLY_FOLDER, "use_closed_bar": True},
    "M": {"folder": MONTHLY_FOLDER, "use_closed_bar": True},
}


def run_script(relative_path: str) -> None:
    script_path = os.path.join(BASE_DIR, relative_path)
    print(f"\n=== Running: {relative_path} ===")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run([sys.executable, script_path], cwd=BASE_DIR, check=True, env=env)


def load_isin_map() -> Dict[str, str]:
    if not os.path.exists(ISIN_FILE):
        return {}

    isin_df = pd.read_csv(ISIN_FILE)
    isin_df.columns = isin_df.columns.str.upper().str.strip()

    symbol_col = next((column for column in isin_df.columns if "SYMBOL" in column), None)
    isin_col = next((column for column in isin_df.columns if "ISIN" in column), None)

    if symbol_col is None or isin_col is None:
        return {}

    isin_df["SYMBOL_KEY"] = isin_df[symbol_col].astype(str).str.upper().str.strip()
    isin_df["ISIN_VALUE"] = isin_df[isin_col].astype(str).str.strip()

    return isin_df.set_index("SYMBOL_KEY")["ISIN_VALUE"].to_dict()


def load_industry_map() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(INDUSTRY_FILE):
        return {}

    mapping_df = pd.read_csv(INDUSTRY_FILE)
    mapping_df.columns = mapping_df.columns.str.strip()

    symbol_col = next((column for column in mapping_df.columns if column.strip().lower() == "symbol"), None)
    industry_col = next((column for column in mapping_df.columns if "industry" in column.lower()), None)
    sector_col = next((column for column in mapping_df.columns if "sector" in column.lower()), None)

    if symbol_col is None or industry_col is None:
        return {}

    mapping_df["SYMBOL_KEY"] = mapping_df[symbol_col].astype(str).str.upper().str.strip()

    output = {}
    for _, row in mapping_df.iterrows():
        output[row["SYMBOL_KEY"]] = {
            "INDUSTRY": str(row[industry_col]).strip() if pd.notna(row[industry_col]) else "",
            "SECTOR": str(row[sector_col]).strip() if sector_col and pd.notna(row[sector_col]) else "",
        }
    return output


def load_main_industry_map() -> Dict[str, str]:
    if not os.path.exists(MAIN_INDUSTRY_FILE):
        return {}

    mapping_df = pd.read_excel(MAIN_INDUSTRY_FILE)
    mapping_df.columns = mapping_df.columns.str.strip().str.upper()

    symbol_col = next((column for column in mapping_df.columns if "SYMBOL" in column), None)
    main_industry_col = next((column for column in mapping_df.columns if "MAIN_INDUSTRY" in column), None)

    if symbol_col is None or main_industry_col is None:
        return {}

    mapping_df["SYMBOL_KEY"] = mapping_df[symbol_col].astype(str).str.upper().str.strip()
    mapping_df["MAIN_INDUSTRY_VALUE"] = mapping_df[main_industry_col].astype(str).str.strip()

    return mapping_df.drop_duplicates(subset=["SYMBOL_KEY"]).set_index("SYMBOL_KEY")["MAIN_INDUSTRY_VALUE"].to_dict()


def supertrend_tv(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)

    required = {"HIGH", "LOW", "CLOSE"}
    if not required.issubset(df.columns):
        return df

    high = pd.to_numeric(df["HIGH"], errors="coerce")
    low = pd.to_numeric(df["LOW"], errors="coerce")
    close = pd.to_numeric(df["CLOSE"], errors="coerce")

    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    hl2 = (high + low) / 2

    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr

    final_upper = [np.nan] * len(df)
    final_lower = [np.nan] * len(df)
    trend = [np.nan] * len(df)
    supertrend_line = [np.nan] * len(df)

    if df.empty:
        return df

    start = atr.first_valid_index()
    if start is None:
        return df

    final_upper[start] = upperband.iloc[start]
    final_lower[start] = lowerband.iloc[start]
    trend[start] = 1
    supertrend_line[start] = final_lower[start]

    for i in range(start + 1, len(df)):
        if upperband.iloc[i] < final_upper[i - 1] or close.iloc[i - 1] > final_upper[i - 1]:
            final_upper[i] = upperband.iloc[i]
        else:
            final_upper[i] = final_upper[i - 1]

        if lowerband.iloc[i] > final_lower[i - 1] or close.iloc[i - 1] < final_lower[i - 1]:
            final_lower[i] = lowerband.iloc[i]
        else:
            final_lower[i] = final_lower[i - 1]

        if trend[i - 1] == 1:
            trend[i] = -1 if close.iloc[i] < final_lower[i - 1] else 1
        else:
            trend[i] = 1 if close.iloc[i] > final_upper[i - 1] else -1

        supertrend_line[i] = final_lower[i] if trend[i] == 1 else final_upper[i]

    trend_series = pd.Series(trend)

    df["ATR"] = atr
    df["FINAL_UPPER"] = final_upper
    df["FINAL_LOWER"] = final_lower
    df["SUPERTREND"] = supertrend_line
    df["TREND"] = trend
    df["BUY_SIGNAL"] = (trend_series.shift(1) == -1) & (trend_series == 1)
    df["SELL_SIGNAL"] = (trend_series.shift(1) == 1) & (trend_series == -1)

    return df


def load_price_file(folder: str, filename: str) -> Optional[pd.DataFrame]:
    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        return None

    try:
        df = pd.read_csv(path)
    except Exception:
        return None

    if "DATE" not in df.columns:
        return None

    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"]).sort_values("DATE").reset_index(drop=True)

    required = {"OPEN", "HIGH", "LOW", "CLOSE"}
    if not required.issubset(df.columns):
        return None

    return df


def get_signal_index(valid_df: pd.DataFrame, use_closed_bar: bool) -> Optional[int]:
    if valid_df.empty:
        return None

    if use_closed_bar:
        return len(valid_df) - 2 if len(valid_df) >= 3 else None

    return len(valid_df) - 1 if len(valid_df) >= 2 else None


def timeframe_snapshot(st_df: pd.DataFrame, use_closed_bar: bool) -> Dict[str, object]:
    valid = st_df.dropna(subset=["TREND"]).reset_index(drop=True)
    signal_idx = get_signal_index(valid, use_closed_bar)

    if signal_idx is None or signal_idx <= 0:
        return {
            "TREND": None,
            "SIGNAL": "NO_DATA",
            "TRAP": "",
            "SUPERTREND": np.nan,
            "DATE": pd.NaT,
            "CLOSE": np.nan,
            "VOLUME": np.nan,
            "RSI": np.nan,
            "K": np.nan,
            "D": np.nan,
        }

    current = valid.iloc[signal_idx]
    previous = valid.iloc[signal_idx - 1]

    signal = "HOLD"
    if previous["TREND"] == -1 and current["TREND"] == 1:
        signal = "BUY"
    elif previous["TREND"] == 1 and current["TREND"] == -1:
        signal = "SELL"

    trap = ""
    if signal_idx >= 2:
        prev2 = valid.iloc[signal_idx - 2]
        if prev2["TREND"] == -1 and previous["TREND"] == 1 and current["TREND"] == -1:
            trap = "BUY_TRAP"
        elif prev2["TREND"] == 1 and previous["TREND"] == -1 and current["TREND"] == 1:
            trap = "SELL_TRAP"

    return {
        "TREND": int(current["TREND"]) if pd.notna(current["TREND"]) else None,
        "SIGNAL": signal,
        "TRAP": trap,
        "SUPERTREND": float(current["SUPERTREND"]) if pd.notna(current["SUPERTREND"]) else np.nan,
        "DATE": current["DATE"],
        "CLOSE": float(current["CLOSE"]) if pd.notna(current["CLOSE"]) else np.nan,
        "VOLUME": float(current["VOLUME"]) if "VOLUME" in current.index and pd.notna(current["VOLUME"]) else np.nan,
        "RSI": float(current["RSI"]) if "RSI" in current.index and pd.notna(current["RSI"]) else np.nan,
        "K": float(current["K"]) if "K" in current.index and pd.notna(current["K"]) else np.nan,
        "D": float(current["D"]) if "D" in current.index and pd.notna(current["D"]) else np.nan,
    }


def overall_setup(m_signal: str, w_signal: str, d_signal: str, m_trap: str, w_trap: str, d_trap: str) -> str:
    traps = [value for value in [m_trap, w_trap, d_trap] if value]
    if traps:
        return ",".join(traps)

    buys = sum(signal == "BUY" for signal in [m_signal, w_signal, d_signal])
    sells = sum(signal == "SELL" for signal in [m_signal, w_signal, d_signal])

    if buys == 3:
        return "M_W_D_BUY"
    if sells == 3:
        return "M_W_D_SELL"
    if buys > 0 and sells == 0:
        return "BUY_BIAS"
    if sells > 0 and buys == 0:
        return "SELL_BIAS"
    return "HOLD"


def below_threshold(value: object, threshold: float) -> bool:
    return pd.notna(value) and float(value) < threshold


def stochrsi_hierarchy_flags(row: pd.Series, threshold: float = 30.0) -> pd.Series:
    monthly_ok = below_threshold(row["M_K"], threshold) and below_threshold(row["M_D"], threshold)
    weekly_eligible = monthly_ok
    weekly_ok = weekly_eligible and below_threshold(row["W_K"], threshold) and below_threshold(row["W_D"], threshold)
    daily_eligible = weekly_ok
    daily_ok = daily_eligible and below_threshold(row["D_K"], threshold) and below_threshold(row["D_D"], threshold)

    if daily_ok:
        status = "DAILY_BELOW_30"
    elif weekly_ok:
        status = "DAILY_ELIGIBLE"
    elif monthly_ok:
        status = "WEEKLY_ELIGIBLE"
    else:
        status = "NOT_ELIGIBLE"

    return pd.Series(
        {
            "MONTHLY_BELOW_30": monthly_ok,
            "WEEKLY_ELIGIBLE": weekly_eligible,
            "WEEKLY_BELOW_30": weekly_ok,
            "DAILY_ELIGIBLE": daily_eligible,
            "DAILY_BELOW_30": daily_ok,
            "STOCHRSI_STATUS": status,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the M/W/D Supertrend TradingView dashboard."
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip upstream data refresh steps and build the dashboard from existing files only.",
    )
    parser.add_argument(
        "--stochrsi-threshold",
        type=float,
        default=30.0,
        help="Threshold for strict StochRSI K and D checks. Default: 30.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.skip_pipeline:
        for script in PIPELINE_SCRIPTS:
            run_script(script)

    isin_map = load_isin_map()
    industry_map = load_industry_map()
    main_industry_map = load_main_industry_map()

    dashboard_rows: List[Dict[str, object]] = []

    stock_files = sorted(file for file in os.listdir(DAILY_FOLDER) if file.lower().endswith(".csv"))
    print(f"\n=== Building M/W/D supertrend dashboard for {len(stock_files):,} stocks ===")

    for index, file in enumerate(stock_files, start=1):
        symbol = os.path.splitext(file)[0].upper()
        tf_results: Dict[str, Dict[str, object]] = {}

        skip_symbol = False
        for timeframe, config in TIMEFRAME_CONFIG.items():
            df = load_price_file(config["folder"], file)
            if df is None or len(df) < 20:
                skip_symbol = True
                break

            tf_results[timeframe] = timeframe_snapshot(
                supertrend_tv(df, period=10, multiplier=3.0),
                use_closed_bar=bool(config["use_closed_bar"]),
            )

        if skip_symbol:
            continue

        industry_info = industry_map.get(symbol, {})
        main_industry = main_industry_map.get(symbol, "")
        overall = overall_setup(
            tf_results["M"]["SIGNAL"],
            tf_results["W"]["SIGNAL"],
            tf_results["D"]["SIGNAL"],
            tf_results["M"]["TRAP"],
            tf_results["W"]["TRAP"],
            tf_results["D"]["TRAP"],
        )

        dashboard_rows.append(
            {
                "STOCK": symbol,
                "ISIN": isin_map.get(symbol, "UNKNOWN"),
                "MAIN_INDUSTRY": main_industry,
                "INDUSTRY": industry_info.get("INDUSTRY", ""),
                "SECTOR": industry_info.get("SECTOR", ""),
                "D_DATE": tf_results["D"]["DATE"],
                "D_CLOSE": round(tf_results["D"]["CLOSE"], 4) if pd.notna(tf_results["D"]["CLOSE"]) else np.nan,
                "D_VOLUME": round(tf_results["D"]["VOLUME"], 2) if pd.notna(tf_results["D"]["VOLUME"]) else np.nan,
                "D_RSI": round(tf_results["D"]["RSI"], 2) if pd.notna(tf_results["D"]["RSI"]) else np.nan,
                "D_K": round(tf_results["D"]["K"], 2) if pd.notna(tf_results["D"]["K"]) else np.nan,
                "D_D": round(tf_results["D"]["D"], 2) if pd.notna(tf_results["D"]["D"]) else np.nan,
                "D_TREND": tf_results["D"]["TREND"],
                "D_SIGNAL": tf_results["D"]["SIGNAL"],
                "D_TRAP": tf_results["D"]["TRAP"],
                "D_SUPERTREND": round(tf_results["D"]["SUPERTREND"], 4) if pd.notna(tf_results["D"]["SUPERTREND"]) else np.nan,
                "W_DATE": tf_results["W"]["DATE"],
                "W_CLOSE": round(tf_results["W"]["CLOSE"], 4) if pd.notna(tf_results["W"]["CLOSE"]) else np.nan,
                "W_VOLUME": round(tf_results["W"]["VOLUME"], 2) if pd.notna(tf_results["W"]["VOLUME"]) else np.nan,
                "W_RSI": round(tf_results["W"]["RSI"], 2) if pd.notna(tf_results["W"]["RSI"]) else np.nan,
                "W_K": round(tf_results["W"]["K"], 2) if pd.notna(tf_results["W"]["K"]) else np.nan,
                "W_D": round(tf_results["W"]["D"], 2) if pd.notna(tf_results["W"]["D"]) else np.nan,
                "W_TREND": tf_results["W"]["TREND"],
                "W_SIGNAL": tf_results["W"]["SIGNAL"],
                "W_TRAP": tf_results["W"]["TRAP"],
                "W_SUPERTREND": round(tf_results["W"]["SUPERTREND"], 4) if pd.notna(tf_results["W"]["SUPERTREND"]) else np.nan,
                "M_DATE": tf_results["M"]["DATE"],
                "M_CLOSE": round(tf_results["M"]["CLOSE"], 4) if pd.notna(tf_results["M"]["CLOSE"]) else np.nan,
                "M_VOLUME": round(tf_results["M"]["VOLUME"], 2) if pd.notna(tf_results["M"]["VOLUME"]) else np.nan,
                "M_RSI": round(tf_results["M"]["RSI"], 2) if pd.notna(tf_results["M"]["RSI"]) else np.nan,
                "M_K": round(tf_results["M"]["K"], 2) if pd.notna(tf_results["M"]["K"]) else np.nan,
                "M_D": round(tf_results["M"]["D"], 2) if pd.notna(tf_results["M"]["D"]) else np.nan,
                "M_TREND": tf_results["M"]["TREND"],
                "M_SIGNAL": tf_results["M"]["SIGNAL"],
                "M_TRAP": tf_results["M"]["TRAP"],
                "M_SUPERTREND": round(tf_results["M"]["SUPERTREND"], 4) if pd.notna(tf_results["M"]["SUPERTREND"]) else np.nan,
                "OVERALL_SETUP": overall,
            }
        )

        if index % 250 == 0 or index == len(stock_files):
            print(f"Processed {index:,}/{len(stock_files):,} stocks")

    dashboard_df = pd.DataFrame(dashboard_rows)
    if not dashboard_df.empty:
        dashboard_df[
            [
                "MONTHLY_BELOW_30",
                "WEEKLY_ELIGIBLE",
                "WEEKLY_BELOW_30",
                "DAILY_ELIGIBLE",
                "DAILY_BELOW_30",
                "STOCHRSI_STATUS",
            ]
        ] = dashboard_df.apply(
            lambda row: stochrsi_hierarchy_flags(row, args.stochrsi_threshold),
            axis=1,
        )

        recent_m_date = dashboard_df["M_DATE"].dropna().max()
        recent_w_date = dashboard_df["W_DATE"].dropna().max()
        recent_d_date = dashboard_df["D_DATE"].dropna().max()

        dashboard_df["RECENT_DATA_MATCH"] = (
            (dashboard_df["M_DATE"] == recent_m_date)
            & (dashboard_df["W_DATE"] == recent_w_date)
            & (dashboard_df["D_DATE"] == recent_d_date)
        )

        signal_priority = {"BUY": 0, "SELL": 1, "HOLD": 2, "NO_DATA": 3}
        dashboard_df["M_SIGNAL_PRIORITY"] = dashboard_df["M_SIGNAL"].map(signal_priority).fillna(9)
        dashboard_df["W_SIGNAL_PRIORITY"] = dashboard_df["W_SIGNAL"].map(signal_priority).fillna(9)
        dashboard_df["D_SIGNAL_PRIORITY"] = dashboard_df["D_SIGNAL"].map(signal_priority).fillna(9)
        stochrsi_priority = {
            "DAILY_BELOW_30": 0,
            "DAILY_ELIGIBLE": 1,
            "WEEKLY_ELIGIBLE": 2,
            "NOT_ELIGIBLE": 3,
        }
        dashboard_df["RECENT_PRIORITY"] = dashboard_df["RECENT_DATA_MATCH"].astype(int) * -1
        dashboard_df["STOCHRSI_PRIORITY"] = dashboard_df["STOCHRSI_STATUS"].map(stochrsi_priority).fillna(9)
        dashboard_df["TRAP_PRIORITY"] = (
            dashboard_df[["M_TRAP", "W_TRAP", "D_TRAP"]]
            .fillna("")
            .apply(lambda row: 0 if any(value for value in row) else 1, axis=1)
        )
        dashboard_df = dashboard_df.sort_values(
            [
                "RECENT_PRIORITY",
                "STOCHRSI_PRIORITY",
                "TRAP_PRIORITY",
                "M_SIGNAL_PRIORITY",
                "W_SIGNAL_PRIORITY",
                "D_SIGNAL_PRIORITY",
                "STOCK",
            ],
            ascending=[True, True, True, True, True, True, True],
        ).drop(
            columns=[
                "RECENT_PRIORITY",
                "STOCHRSI_PRIORITY",
                "M_SIGNAL_PRIORITY",
                "W_SIGNAL_PRIORITY",
                "D_SIGNAL_PRIORITY",
                "TRAP_PRIORITY",
            ]
        )

    dashboard_df.to_csv(DASHBOARD_OUTPUT, index=False)

    signals_df = dashboard_df[
        (dashboard_df["M_SIGNAL"].isin(["BUY", "SELL"]))
        | (dashboard_df["W_SIGNAL"].isin(["BUY", "SELL"]))
        | (dashboard_df["D_SIGNAL"].isin(["BUY", "SELL"]))
        | (dashboard_df["M_TRAP"] != "")
        | (dashboard_df["W_TRAP"] != "")
        | (dashboard_df["D_TRAP"] != "")
    ].copy()
    signals_df.to_csv(SIGNALS_OUTPUT, index=False)

    recent_stochrsi_df = dashboard_df[
        dashboard_df["RECENT_DATA_MATCH"] & dashboard_df["MONTHLY_BELOW_30"]
    ].copy()
    recent_stochrsi_df.to_csv(STOCHRSI_RECENT_OUTPUT, index=False)

    daily_eligible_df = dashboard_df[
        dashboard_df["RECENT_DATA_MATCH"] & dashboard_df["WEEKLY_BELOW_30"]
    ].copy()
    daily_eligible_df.to_csv(STOCHRSI_DAILY_ELIGIBLE_OUTPUT, index=False)

    daily_below_30_df = dashboard_df[
        dashboard_df["RECENT_DATA_MATCH"] & dashboard_df["DAILY_BELOW_30"]
    ].copy()
    daily_below_30_df.to_csv(STOCHRSI_DAILY_BELOW_30_OUTPUT, index=False)

    print("\nPipeline completed")
    print(f"Dashboard: {DASHBOARD_OUTPUT}")
    print(f"Signals only: {SIGNALS_OUTPUT}")
    if not dashboard_df.empty:
        print(
            "Recent reference dates:",
            f"M={dashboard_df['M_DATE'].dropna().max().date()}",
            f"W={dashboard_df['W_DATE'].dropna().max().date()}",
            f"D={dashboard_df['D_DATE'].dropna().max().date()}",
        )
        print(f"Recent StochRSI monthly-pass dashboard: {STOCHRSI_RECENT_OUTPUT} ({len(recent_stochrsi_df):,} rows)")
        print(f"Recent StochRSI daily-eligible dashboard: {STOCHRSI_DAILY_ELIGIBLE_OUTPUT} ({len(daily_eligible_df):,} rows)")
        print(f"Recent StochRSI daily-below-30 dashboard: {STOCHRSI_DAILY_BELOW_30_OUTPUT} ({len(daily_below_30_df):,} rows)")


if __name__ == "__main__":
    main()
