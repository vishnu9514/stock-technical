import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
input_folder = os.path.join(BASE_DIR, "data", "atr_data")
output_folder = os.path.join(BASE_DIR, "data", "trend_data")

os.makedirs(output_folder, exist_ok=True)

# -----------------------------------
# TREND ENGINE (FINAL VERSION)
# -----------------------------------

def compute_trend(df, period=10, multiplier=1.2):

    df = df.copy()

    high = df["HIGH"]
    low = df["LOW"]
    close = df["CLOSE"]

    # --- TRUE RANGE ---
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)

    # --- ATR (TradingView style RMA) ---
    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    # --- BASIC BANDS ---
    hl2 = (high + low) / 2
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr

    # -----------------------------------
    # INITIALIZE ARRAYS
    # -----------------------------------

    final_upper = [np.nan] * len(df)
    final_lower = [np.nan] * len(df)
    trend = [np.nan] * len(df)

    # -----------------------------------
    # FIND FIRST VALID INDEX
    # -----------------------------------

    start = atr.first_valid_index()

    if start is None:
        return df

    start = df.index.get_loc(start)

    # initialize first valid row
    final_upper[start] = upperband.iloc[start]
    final_lower[start] = lowerband.iloc[start]
    trend[start] = 1

    # -----------------------------------
    # MAIN LOOP
    # -----------------------------------

    for i in range(start + 1, len(df)):

        # FINAL UPPER
        if upperband.iloc[i] < final_upper[i-1] or close.iloc[i-1] > final_upper[i-1]:
            final_upper[i] = upperband.iloc[i]
        else:
            final_upper[i] = final_upper[i-1]

        # FINAL LOWER
        if lowerband.iloc[i] > final_lower[i-1] or close.iloc[i-1] < final_lower[i-1]:
            final_lower[i] = lowerband.iloc[i]
        else:
            final_lower[i] = final_lower[i-1]

        # TREND SWITCH
        if trend[i-1] == 1:
            if close.iloc[i] < final_lower[i-1]:
                trend[i] = -1
            else:
                trend[i] = 1
        else:
            if close.iloc[i] > final_upper[i-1]:
                trend[i] = 1
            else:
                trend[i] = -1

    # -----------------------------------
    # SAVE RESULTS
    # -----------------------------------

    df["ATR_TV"] = atr
    df["FINAL_UPPER"] = final_upper
    df["FINAL_LOWER"] = final_lower
    df["TREND"] = trend

    return df

# -----------------------------------
# PROCESS ALL FILES
# -----------------------------------

for file in os.listdir(input_folder):

    path = os.path.join(input_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    required = ["DATE", "HIGH", "LOW", "CLOSE"]
    if not all(col in df.columns for col in required):
        continue

    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE")

    if len(df) < 50:
        continue

    try:
        df = compute_trend(df, period=10, multiplier=1.0)

        df.to_csv(os.path.join(output_folder, file), index=False)

    except Exception as e:
        print(f"Error in {file}: {e}")
        continue

print("🔥 FINAL TREND ENGINE COMPLETED")