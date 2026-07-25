import os

import numpy as np
import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOLDERS = [
    "nse_stocks",
    "nse_weekly",
    "nse_monthly",
    "nse_quarterly",
]

RSI_LENGTH = 14
STOCH_LENGTH = 14
K_SMOOTH = 3
D_SMOOTH = 3


def tradingview_rsi(close: pd.Series, length: int = RSI_LENGTH) -> pd.Series:
    close = pd.to_numeric(close, errors="coerce")
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi.where(close.notna())


def tradingview_stochrsi(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    rsi = tradingview_rsi(df["CLOSE"], RSI_LENGTH)
    rsi_min = rsi.rolling(STOCH_LENGTH, min_periods=STOCH_LENGTH).min()
    rsi_max = rsi.rolling(STOCH_LENGTH, min_periods=STOCH_LENGTH).max()

    rsi_range = (rsi_max - rsi_min).replace(0, np.nan)
    stoch = ((rsi - rsi_min) / rsi_range) * 100

    k = stoch.rolling(K_SMOOTH, min_periods=K_SMOOTH).mean()
    d = k.rolling(D_SMOOTH, min_periods=D_SMOOTH).mean()

    df["RSI"] = rsi
    df["STOCHRSI"] = stoch
    df["K"] = k
    df["D"] = d

    return df


def main() -> None:
    for folder in FOLDERS:
        folder_path = os.path.join(BASE_DIR, "data", folder)
        if not os.path.exists(folder_path):
            print(f"Skipping missing folder: {folder_path}")
            continue

        files = [file for file in os.listdir(folder_path) if file.lower().endswith(".csv")]
        print(f"Processing: {folder} ({len(files):,} files)")

        for file in files:
            path = os.path.join(folder_path, file)

            try:
                df = pd.read_csv(path)
            except Exception:
                continue

            if "CLOSE" not in df.columns:
                continue

            df = tradingview_stochrsi(df)
            df.to_csv(path, index=False)

        print(f"Completed: {folder}")

    print("TradingView-style StochRSI completed")


if __name__ == "__main__":
    main()
