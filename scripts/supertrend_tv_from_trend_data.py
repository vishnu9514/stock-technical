import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
input_folder = os.path.join(BASE_DIR, "data", "trend_data")

# ===================================
# TRUE TRADINGVIEW SUPERTREND
# ===================================

def supertrend_tv(df, period=10, multiplier=1.8):

    df = df.copy()

    high = df["HIGH"]
    low = df["LOW"]
    close = df["CLOSE"]

    # --- TR ---
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)

    # --- ATR ---
    atr = tr.rolling(period).mean()

    # --- BASIC BANDS ---
    hl2 = (high + low) / 2
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr

    # --- FINAL BANDS + TREND ---
    final_upper = upperband.copy()
    final_lower = lowerband.copy()

    trend = [1]
    st = [np.nan]

    for i in range(1, len(df)):

        # FINAL UPPER
        if upperband.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = upperband.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]

        # FINAL LOWER
        if lowerband.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = lowerband.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]

        # TREND SWITCH (CRITICAL FIX)
        if trend[-1] == 1:
            if close.iloc[i] < final_lower.iloc[i-1]:
                trend.append(-1)
            else:
                trend.append(1)
        else:
            if close.iloc[i] > final_upper.iloc[i-1]:
                trend.append(1)
            else:
                trend.append(-1)

        # SUPERTREND VALUE
        st.append(final_lower.iloc[i] if trend[-1] == 1 else final_upper.iloc[i])

    df["TREND"] = trend
    df["SUPERTREND"] = st

    return df

# ===================================
# RESAMPLE
# ===================================

def resample_df(df, freq):

    o = df["OPEN"].resample(freq).first()
    h = df["HIGH"].resample(freq).max()
    l = df["LOW"].resample(freq).min()
    c = df["CLOSE"].resample(freq).last()
    v = df["VOLUME"].resample(freq).sum()

    out = pd.concat([o, h, l, c, v], axis=1)
    out.columns = ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]

    return out.dropna()

# ===================================
# PROCESS
# ===================================

results = []

for file in os.listdir(input_folder):

    path = os.path.join(input_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "DATE" not in df.columns:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE").set_index("DATE")

    if len(df) < 200:
        continue

    symbol = file.replace(".csv", "")

    try:
        d = supertrend_tv(df)

        w = supertrend_tv(resample_df(df, "W"))
        m = supertrend_tv(resample_df(df, "ME"))
        q = supertrend_tv(resample_df(df, "QE"))

        results.append({
            "STOCK": symbol,

            "D_TREND": d["TREND"].iloc[-2],
            "W_TREND": w["TREND"].iloc[-2],
            "M_TREND": m["TREND"].iloc[-2],
            "Q_TREND": q["TREND"].iloc[-2],
        })

    except:
        continue

# ===================================
# OUTPUT
# ===================================

df_out = pd.DataFrame(results)

output_path = os.path.join(BASE_DIR, "data", "supertrend_tv_dashboard.csv")
df_out.to_csv(output_path, index=False)

print("\n🔥 TRUE TRADINGVIEW SUPERTREND GENERATED\n")
print(df_out.head(20))