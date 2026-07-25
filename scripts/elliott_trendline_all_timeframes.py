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
# SWING DETECTION
# -----------------------------------

def find_swings(df, window=7):

    df["SWING_HIGH"] = df["HIGH"][
        (df["HIGH"] == df["HIGH"].rolling(window, center=True).max())
    ]

    df["SWING_LOW"] = df["LOW"][
        (df["LOW"] == df["LOW"].rolling(window, center=True).min())
    ]

    return df

# -----------------------------------
# ELLIOTT TRENDLINE
# -----------------------------------

def elliott_trendline(df):

    df["ELLIOTT_TRENDLINE"] = np.nan

    swing_lows = df.dropna(subset=["SWING_LOW"])

    if len(swing_lows) < 3:
        return df

    last_swings = swing_lows.tail(3)

    # check higher low structure
    if not (
        last_swings["SWING_LOW"].iloc[2] >
        last_swings["SWING_LOW"].iloc[1] >
        last_swings["SWING_LOW"].iloc[0]
    ):
        return df

    x1 = last_swings.index[1]
    x2 = last_swings.index[2]

    y1 = last_swings["SWING_LOW"].iloc[1]
    y2 = last_swings["SWING_LOW"].iloc[2]

    slope = (y2 - y1) / (x2 - x1)

    for i in range(x2, len(df)):
        df.loc[i, "ELLIOTT_TRENDLINE"] = y2 + slope * (i - x2)

    return df

# -----------------------------------
# MAIN PROCESS
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

        if "HIGH" not in df.columns:
            continue

        df = df.sort_values("DATE")

        df = find_swings(df)
        df = elliott_trendline(df)

        df.to_csv(path, index=False)

        print("Updated:", file)

print("\n✅ Elliott trendlines added to all timeframes")