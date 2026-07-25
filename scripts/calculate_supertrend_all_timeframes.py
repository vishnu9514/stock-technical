import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

folders = [
    "nse_stocks",     # Daily
    "nse_weekly",     # Weekly
    "nse_monthly",    # Monthly
    "nse_quarterly"   # 3M
]

# -----------------------------------
# SUPERTREND FUNCTION (STABLE VERSION)
# -----------------------------------

def add_supertrend(df, period=10, multiplier=3):

    df = df.copy()

    # True Range
    df["H-L"] = df["HIGH"] - df["LOW"]
    df["H-PC"] = abs(df["HIGH"] - df["CLOSE"].shift(1))
    df["L-PC"] = abs(df["LOW"] - df["CLOSE"].shift(1))

    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)

    # ATR
    df["ATR"] = df["TR"].rolling(period).mean()

    # Bands
    hl2 = (df["HIGH"] + df["LOW"]) / 2
    df["UPPER_BAND"] = hl2 + multiplier * df["ATR"]
    df["LOWER_BAND"] = hl2 - multiplier * df["ATR"]

    # Supertrend columns
    df["SUPERTREND"] = np.nan
    df["ST_DIRECTION"] = 1  # 1 = bullish, -1 = bearish

    for i in range(1, len(df)):

        if df["CLOSE"].iloc[i] > df["UPPER_BAND"].iloc[i-1]:
            df.loc[i, "ST_DIRECTION"] = 1

        elif df["CLOSE"].iloc[i] < df["LOWER_BAND"].iloc[i-1]:
            df.loc[i, "ST_DIRECTION"] = -1

        else:
            df.loc[i, "ST_DIRECTION"] = df["ST_DIRECTION"].iloc[i-1]

            if df["ST_DIRECTION"].iloc[i] == 1:
                df.loc[i, "LOWER_BAND"] = max(
                    df["LOWER_BAND"].iloc[i],
                    df["LOWER_BAND"].iloc[i-1]
                )
            else:
                df.loc[i, "UPPER_BAND"] = min(
                    df["UPPER_BAND"].iloc[i],
                    df["UPPER_BAND"].iloc[i-1]
                )

        # Set supertrend line
        if df["ST_DIRECTION"].iloc[i] == 1:
            df.loc[i, "SUPERTREND"] = df["LOWER_BAND"].iloc[i]
        else:
            df.loc[i, "SUPERTREND"] = df["UPPER_BAND"].iloc[i]

    return df

# -----------------------------------
# PROCESS ALL TIMEFRAMES
# -----------------------------------

for folder in folders:

    folder_path = os.path.join(BASE_DIR, "data", folder)

    print(f"\nProcessing {folder}...")

    files = os.listdir(folder_path)

    for file in files:

        path = os.path.join(folder_path, file)

        try:
            df = pd.read_csv(path)
        except:
            continue

        if "CLOSE" not in df.columns:
            continue

        df = df.sort_values("DATE")

        df = add_supertrend(df)

        df.to_csv(path, index=False)

        print("Updated:", file)

print("\n✅ Supertrend added to all timeframes (D/W/M/3M)")