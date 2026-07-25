from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FOLDERS = [
    BASE_DIR / "data" / "nse_stocks",
    BASE_DIR / "data" / "tr_data",
]
OUTPUT_DIR = BASE_DIR / "data" / "backtests" / "supertrend_tv_5y"

YEARS_BACK = 5
PERIOD = 10
MULTIPLIER = 3.0
CAPITAL_PER_TRADE = 100000.0
MIN_BARS = 50
LOG_INTERVAL = 250

TIMEFRAME_RULES: dict[str, str | None] = {
    "D": None,
    "W": "W-FRI",
    "M": "ME",
    "Q": "QE",
}

MIN_BARS_BY_TIMEFRAME: dict[str, int] = {
    "D": 50,
    "W": 50,
    "M": 24,
    "Q": 12,
}


def resolve_data_folder() -> Path:
    for folder in DATA_FOLDERS:
        if folder.exists():
            return folder
    raise FileNotFoundError(f"No stock data folder found in: {DATA_FOLDERS}")


def safe_to_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_csv(path, index=False)
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_fallback{path.suffix}")
        df.to_csv(fallback, index=False)
        print(f"Permission denied writing {path}; saved fallback file to {fallback}")
        return fallback


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]
    if any(col not in df.columns for col in required):
        return pd.DataFrame()

    out = df.copy()
    out["DATE"] = pd.to_datetime(out["DATE"], errors="coerce")
    out = out.dropna(subset=["DATE"]).sort_values("DATE").drop_duplicates(subset=["DATE"], keep="last")

    for col in ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=["OPEN", "HIGH", "LOW", "CLOSE"]).reset_index(drop=True)
    if "VOLUME" not in out.columns:
        out["VOLUME"] = 0.0
    else:
        out["VOLUME"] = out["VOLUME"].fillna(0.0)

    return out[["DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]]


def supertrend_tv(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)

    required = {"HIGH", "LOW", "CLOSE"}
    if not required.issubset(df.columns) or df.empty:
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
    df["TREND"] = trend_series
    df["BUY_SIGNAL"] = (trend_series.shift(1) == -1) & (trend_series == 1)
    df["SELL_SIGNAL"] = (trend_series.shift(1) == 1) & (trend_series == -1)

    return df


def resample_ohlcv(df: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    if rule is None:
        return df.copy()

    indexed = df.copy().set_index("DATE")
    last_trade_date = indexed.index.to_series().resample(rule).last().rename("DATE")
    resampled = pd.concat(
        [
            last_trade_date,
            indexed["OPEN"].resample(rule).first().rename("OPEN"),
            indexed["HIGH"].resample(rule).max().rename("HIGH"),
            indexed["LOW"].resample(rule).min().rename("LOW"),
            indexed["CLOSE"].resample(rule).last().rename("CLOSE"),
            indexed["VOLUME"].resample(rule).sum().rename("VOLUME"),
        ],
        axis=1,
    )
    return resampled.dropna().reset_index(drop=True)


def timeframe_bars(df: pd.DataFrame, rule: str | None, cutoff: pd.Timestamp) -> pd.DataFrame:
    bars = resample_ohlcv(df, rule)
    bars = bars[bars["DATE"] >= cutoff].reset_index(drop=True)
    return bars


def fill_price(df: pd.DataFrame, idx: int) -> float:
    open_price = df.at[idx, "OPEN"]
    if pd.notna(open_price) and open_price > 0:
        return float(open_price)
    return float(df.at[idx, "CLOSE"])


def enrich_exit_periods(exit_date: pd.Timestamp) -> dict[str, object]:
    iso = exit_date.isocalendar()
    return {
        "EXIT_DAY": exit_date.strftime("%Y-%m-%d"),
        "EXIT_WEEK": f"{int(iso.year)}-W{int(iso.week):02d}",
        "EXIT_MONTH": exit_date.strftime("%Y-%m"),
        "EXIT_QUARTER": f"{exit_date.year}-Q{((exit_date.month - 1) // 3) + 1}",
        "EXIT_YEAR": int(exit_date.year),
    }


def record_trade(
    symbol: str,
    timeframe: str,
    entry_signal_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    entry_price: float,
    exit_signal_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    exit_price: float,
    entry_idx: int,
    exit_idx: int,
) -> dict[str, object]:
    trade_return = (exit_price - entry_price) / entry_price
    return_pct = trade_return * 100
    pnl_amount = trade_return * CAPITAL_PER_TRADE

    return {
        "STOCK": symbol,
        "TIMEFRAME": timeframe,
        "ENTRY_SIGNAL_DATE": entry_signal_date,
        "ENTRY_DATE": entry_date,
        "ENTRY_PRICE": round(entry_price, 2),
        "EXIT_SIGNAL_DATE": exit_signal_date,
        "EXIT_DATE": exit_date,
        "EXIT_PRICE": round(exit_price, 2),
        "RETURN_PCT": round(return_pct, 2),
        "RETURN_DECIMAL": trade_return,
        "PNL_AMOUNT": round(pnl_amount, 2),
        "PROFIT_AMOUNT": round(max(pnl_amount, 0.0), 2),
        "LOSS_AMOUNT": round(min(pnl_amount, 0.0), 2),
        "PROFIT_PCT": round(max(return_pct, 0.0), 2),
        "LOSS_PCT": round(min(return_pct, 0.0), 2),
        "PROFIT": pnl_amount > 0,
        "DAYS_HELD": int((exit_date - entry_date).days),
        "BARS_HELD": int(max(exit_idx - entry_idx, 0) + 1),
        **enrich_exit_periods(exit_date),
    }


def backtest_timeframe(symbol: str, timeframe: str, bars: pd.DataFrame) -> list[dict[str, object]]:
    min_bars = MIN_BARS_BY_TIMEFRAME.get(timeframe, MIN_BARS)
    if len(bars) < min_bars:
        return []

    st = supertrend_tv(bars, period=PERIOD, multiplier=MULTIPLIER)
    if st.empty:
        return []

    trades: list[dict[str, object]] = []
    in_position = False
    entry_idx: int | None = None
    entry_signal_date: pd.Timestamp | None = None
    entry_date: pd.Timestamp | None = None
    entry_price: float | None = None

    for signal_idx in range(len(st)):
        row = st.iloc[signal_idx]

        if not in_position and bool(row["BUY_SIGNAL"]):
            fill_idx = signal_idx + 1
            if fill_idx >= len(st):
                continue

            entry_idx = fill_idx
            entry_signal_date = pd.Timestamp(row["DATE"])
            entry_date = pd.Timestamp(st.at[fill_idx, "DATE"])
            entry_price = fill_price(st, fill_idx)
            in_position = True

        elif in_position and bool(row["SELL_SIGNAL"]) and entry_idx is not None and signal_idx > entry_idx:
            fill_idx = signal_idx + 1
            if fill_idx < len(st):
                exit_idx = fill_idx
                exit_date = pd.Timestamp(st.at[fill_idx, "DATE"])
                exit_price = fill_price(st, fill_idx)
            else:
                exit_idx = signal_idx
                exit_date = pd.Timestamp(row["DATE"])
                exit_price = float(row["CLOSE"])

            if entry_signal_date is not None and entry_date is not None and entry_price is not None and entry_price > 0:
                trades.append(
                    record_trade(
                        symbol=symbol,
                        timeframe=timeframe,
                        entry_signal_date=entry_signal_date,
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_signal_date=pd.Timestamp(row["DATE"]),
                        exit_date=exit_date,
                        exit_price=exit_price,
                        entry_idx=entry_idx,
                        exit_idx=exit_idx,
                    )
                )

            in_position = False
            entry_idx = None
            entry_signal_date = None
            entry_date = None
            entry_price = None

    if in_position and entry_idx is not None and entry_signal_date is not None and entry_date is not None and entry_price is not None:
        exit_idx = len(st) - 1
        exit_date = pd.Timestamp(st.at[exit_idx, "DATE"])
        exit_price = float(st.at[exit_idx, "CLOSE"])
        if entry_price > 0:
            trades.append(
                record_trade(
                    symbol=symbol,
                    timeframe=timeframe,
                    entry_signal_date=entry_signal_date,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_signal_date=exit_date,
                    exit_date=exit_date,
                    exit_price=exit_price,
                    entry_idx=entry_idx,
                    exit_idx=exit_idx,
                )
            )

    return trades


def metric_block(df: pd.DataFrame) -> dict[str, object]:
    total_trades = int(len(df))
    winning_trades = int(df["PROFIT"].sum()) if total_trades else 0
    losing_trades = total_trades - winning_trades

    gross_profit_pct = float(df["PROFIT_PCT"].sum()) if total_trades else 0.0
    gross_loss_pct = float(df["LOSS_PCT"].sum()) if total_trades else 0.0
    gross_profit_amount = float(df["PROFIT_AMOUNT"].sum()) if total_trades else 0.0
    gross_loss_amount = float(df["LOSS_AMOUNT"].sum()) if total_trades else 0.0

    profit_factor = np.nan
    if gross_loss_amount != 0:
        profit_factor = gross_profit_amount / abs(gross_loss_amount)

    compounded_return = np.nan
    if total_trades and (1 + df["RETURN_DECIMAL"]).gt(0).all():
        log_growth = np.log1p(df["RETURN_DECIMAL"]).sum()
        if abs(log_growth) <= 25:
            compounded_return = np.expm1(log_growth) * 100

    avg_win_pct = df.loc[df["PROFIT"], "RETURN_PCT"].mean() if winning_trades else np.nan
    avg_loss_pct = df.loc[~df["PROFIT"], "RETURN_PCT"].mean() if losing_trades else np.nan

    return {
        "TOTAL_TRADES": total_trades,
        "WINNING_TRADES": winning_trades,
        "LOSING_TRADES": losing_trades,
        "WIN_RATE_PCT": round((winning_trades / total_trades) * 100, 2) if total_trades else np.nan,
        "LOSS_RATE_PCT": round((losing_trades / total_trades) * 100, 2) if total_trades else np.nan,
        "PROFITABLE_TRADE_PROBABILITY_PCT": round((winning_trades / total_trades) * 100, 2) if total_trades else np.nan,
        "LOSING_TRADE_PROBABILITY_PCT": round((losing_trades / total_trades) * 100, 2) if total_trades else np.nan,
        "AVG_RETURN_PCT": round(df["RETURN_PCT"].mean(), 2) if total_trades else np.nan,
        "MEDIAN_RETURN_PCT": round(df["RETURN_PCT"].median(), 2) if total_trades else np.nan,
        "AVG_WIN_PCT": round(avg_win_pct, 2) if pd.notna(avg_win_pct) else np.nan,
        "AVG_LOSS_PCT": round(avg_loss_pct, 2) if pd.notna(avg_loss_pct) else np.nan,
        "MAX_WIN_PCT": round(df["RETURN_PCT"].max(), 2) if total_trades else np.nan,
        "MAX_LOSS_PCT": round(df["RETURN_PCT"].min(), 2) if total_trades else np.nan,
        "GROSS_PROFIT_PCT": round(gross_profit_pct, 2),
        "GROSS_LOSS_PCT": round(gross_loss_pct, 2),
        "NET_RETURN_PCT": round(float(df["RETURN_PCT"].sum()), 2) if total_trades else 0.0,
        "COMPOUNDED_RETURN_PCT": round(compounded_return, 2) if pd.notna(compounded_return) else np.nan,
        "TOTAL_PROFIT_AMOUNT": round(gross_profit_amount, 2),
        "TOTAL_LOSS_AMOUNT": round(gross_loss_amount, 2),
        "NET_PROFIT_AMOUNT": round(float(df["PNL_AMOUNT"].sum()), 2) if total_trades else 0.0,
        "AVG_PROFIT_AMOUNT": round(df["PNL_AMOUNT"].mean(), 2) if total_trades else np.nan,
        "AVG_WIN_AMOUNT": round(df.loc[df["PROFIT"], "PNL_AMOUNT"].mean(), 2) if winning_trades else np.nan,
        "AVG_LOSS_AMOUNT": round(df.loc[~df["PROFIT"], "PNL_AMOUNT"].mean(), 2) if losing_trades else np.nan,
        "PROFIT_FACTOR": round(profit_factor, 4) if pd.notna(profit_factor) else np.nan,
        "AVG_HOLD_DAYS": round(df["DAYS_HELD"].mean(), 2) if total_trades else np.nan,
        "AVG_HOLD_BARS": round(df["BARS_HELD"].mean(), 2) if total_trades else np.nan,
    }


def build_statement(trades_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if trades_df.empty:
        cols = group_cols + list(metric_block(pd.DataFrame(columns=["PROFIT", "PROFIT_PCT", "LOSS_PCT", "RETURN_PCT", "RETURN_DECIMAL", "PROFIT_AMOUNT", "LOSS_AMOUNT", "PNL_AMOUNT", "DAYS_HELD", "BARS_HELD"])).keys())
        return pd.DataFrame(columns=cols)

    rows: list[dict[str, object]] = []
    if not group_cols:
        rows.append(metric_block(trades_df))
        return pd.DataFrame(rows)

    for keys, group in trades_df.groupby(group_cols, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {col: value for col, value in zip(group_cols, keys)}
        row.update(metric_block(group))
        rows.append(row)

    return pd.DataFrame(rows)


def run_backtest() -> dict[str, Path]:
    data_folder = resolve_data_folder()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stock_files = sorted(data_folder.glob("*.csv"))
    if not stock_files:
        raise FileNotFoundError(f"No CSV files found in {data_folder}")

    all_trades: list[dict[str, object]] = []
    processed_files = 0
    skipped_files = 0

    print(f"Using data folder: {data_folder}")
    print(f"Found {len(stock_files)} stock files")
    print(f"Running 5-year TradingView-style Supertrend backtest with period={PERIOD}, multiplier={MULTIPLIER}")

    for idx, path in enumerate(stock_files, start=1):
        try:
            raw_df = pd.read_csv(path)
        except Exception:
            skipped_files += 1
            continue

        stock_df = normalize_ohlcv(raw_df)
        if stock_df.empty:
            skipped_files += 1
            continue

        cutoff = stock_df["DATE"].max() - pd.DateOffset(years=YEARS_BACK)
        symbol = path.stem.upper()

        for timeframe, rule in TIMEFRAME_RULES.items():
            bars = timeframe_bars(stock_df, rule, cutoff)
            all_trades.extend(backtest_timeframe(symbol, timeframe, bars))

        processed_files += 1
        if idx % LOG_INTERVAL == 0:
            print(f"Processed {idx}/{len(stock_files)} files | valid={processed_files} | trades={len(all_trades)}")

    trades_df = pd.DataFrame(all_trades)
    if trades_df.empty:
        raise RuntimeError("No trades were generated. Check the price history and Supertrend settings.")

    trades_df = trades_df.sort_values(["TIMEFRAME", "EXIT_DATE", "STOCK"]).reset_index(drop=True)

    start_date = trades_df["ENTRY_DATE"].min()
    end_date = trades_df["EXIT_DATE"].max()

    overall_summary = build_statement(trades_df, [])
    overall_summary.insert(0, "SCOPE", "ALL_STOCKS_ALL_TIMEFRAMES")
    overall_summary["DATA_FOLDER"] = str(data_folder)
    overall_summary["START_DATE"] = start_date.strftime("%Y-%m-%d")
    overall_summary["END_DATE"] = end_date.strftime("%Y-%m-%d")
    overall_summary["YEARS_BACK"] = YEARS_BACK
    overall_summary["SUPER_TREND_PERIOD"] = PERIOD
    overall_summary["SUPER_TREND_MULTIPLIER"] = MULTIPLIER
    overall_summary["CAPITAL_PER_TRADE"] = CAPITAL_PER_TRADE
    overall_summary["VALID_STOCK_FILES"] = processed_files
    overall_summary["SKIPPED_FILES"] = skipped_files

    timeframe_summary = build_statement(trades_df, ["TIMEFRAME"])
    timeframe_summary["START_DATE"] = start_date.strftime("%Y-%m-%d")
    timeframe_summary["END_DATE"] = end_date.strftime("%Y-%m-%d")

    stock_summary = build_statement(trades_df, ["TIMEFRAME", "STOCK"])
    yearly_statement = build_statement(trades_df, ["TIMEFRAME", "EXIT_YEAR"])
    quarterly_statement = build_statement(trades_df, ["TIMEFRAME", "EXIT_QUARTER"])
    monthly_statement = build_statement(trades_df, ["TIMEFRAME", "EXIT_MONTH"])
    weekly_statement = build_statement(trades_df, ["TIMEFRAME", "EXIT_WEEK"])
    daily_statement = build_statement(trades_df, ["TIMEFRAME", "EXIT_DAY"])

    outputs = {
        "trades": safe_to_csv(trades_df, OUTPUT_DIR / "supertrend_tv_trades_5y_all_timeframes.csv"),
        "overall_summary": safe_to_csv(overall_summary, OUTPUT_DIR / "supertrend_tv_overall_summary_5y.csv"),
        "timeframe_summary": safe_to_csv(timeframe_summary, OUTPUT_DIR / "supertrend_tv_timeframe_summary_5y.csv"),
        "stock_summary": safe_to_csv(stock_summary, OUTPUT_DIR / "supertrend_tv_stock_summary_5y.csv"),
        "yearly_statement": safe_to_csv(yearly_statement, OUTPUT_DIR / "supertrend_tv_yearly_statement_5y.csv"),
        "quarterly_statement": safe_to_csv(quarterly_statement, OUTPUT_DIR / "supertrend_tv_quarterly_statement_5y.csv"),
        "monthly_statement": safe_to_csv(monthly_statement, OUTPUT_DIR / "supertrend_tv_monthly_statement_5y.csv"),
        "weekly_statement": safe_to_csv(weekly_statement, OUTPUT_DIR / "supertrend_tv_weekly_statement_5y.csv"),
        "daily_statement": safe_to_csv(daily_statement, OUTPUT_DIR / "supertrend_tv_daily_statement_5y.csv"),
    }

    print("\nBacktest complete")
    print(f"Valid stock files processed: {processed_files}")
    print(f"Skipped files: {skipped_files}")
    print(f"Total trades generated: {len(trades_df)}")
    print(f"Output directory: {OUTPUT_DIR}")

    print("\nTimeframe summary:")
    print(timeframe_summary.to_string(index=False))

    return outputs


def main() -> None:
    run_backtest()


if __name__ == "__main__":
    main()
