import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
isin_file = os.path.join(BASE_DIR, "data", "EQUITY_L.csv")

# -----------------------------------
# LOAD ISIN
# -----------------------------------

isin_df = pd.read_csv(isin_file)
isin_df.columns = isin_df.columns.str.upper()

symbol_col = [c for c in isin_df.columns if "SYMBOL" in c][0]
isin_col = [c for c in isin_df.columns if "ISIN" in c][0]

isin_df["SYMBOL"] = isin_df[symbol_col].astype(str).str.upper().str.strip()
isin_map = isin_df.set_index("SYMBOL")[isin_col].to_dict()

# -----------------------------------
# STOCH RSI (TradingView Style)
# -----------------------------------

def compute_stochrsi(df, rsi_period=14, stoch_period=14, k=3, d=3):

    close = df["CLOSE"]

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/rsi_period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    min_rsi = rsi.rolling(stoch_period).min()
    max_rsi = rsi.rolling(stoch_period).max()

    stoch = (rsi - min_rsi) / (max_rsi - min_rsi)

    k_line = stoch.rolling(k).mean() * 100
    d_line = k_line.rolling(d).mean()

    df["K"] = k_line
    df["D"] = d_line

    return df

# -----------------------------------
# RESAMPLE
# -----------------------------------

def resample_df(df, freq):

    o = df["OPEN"].resample(freq).first()
    h = df["HIGH"].resample(freq).max()
    l = df["LOW"].resample(freq).min()
    c = df["CLOSE"].resample(freq).last()
    v = df["VOLUME"].resample(freq).sum()

    out = pd.concat([o, h, l, c, v], axis=1)
    out.columns = ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]

    return out.dropna()

# -----------------------------------
# PROCESS
# -----------------------------------

results = []

for file in os.listdir(data_folder):

    path = os.path.join(data_folder, file)

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

    symbol = file.replace(".csv", "").upper()
    isin = isin_map.get(symbol, "UNKNOWN")

    try:
        # -----------------------------
        # MONTHLY FILTER
        # -----------------------------
        m = compute_stochrsi(resample_df(df, "ME"))
        m_k = m["K"].iloc[-2]
        m_d = m["D"].iloc[-2]

        if not (m_k < 30 and m_d < 30):
            continue

        # -----------------------------
        # WEEKLY FILTER
        # -----------------------------
        w = compute_stochrsi(resample_df(df, "W"))
        w_k = w["K"].iloc[-2]
        w_d = w["D"].iloc[-2]

        if not (w_k < 30 and w_d < 30):
            continue

        # -----------------------------
        # DAILY (NO FILTER)
        # -----------------------------
        d = compute_stochrsi(df)
        d_k = d["K"].iloc[-2]
        d_d = d["D"].iloc[-2]

        # --------------------------------
        # ENTRY STAGE CLASSIFICATION
        # --------------------------------

        stage = "WAIT"

        if d_k < 30 and d_d < 30:
            stage = "DEEP_OVERSOLD"

        elif d_k > d_d and d_k < 40:
            stage = "EARLY_REVERSAL"

        elif d_k > 50:
            stage = "MOMENTUM_START"

        results.append({
            "STOCK": symbol,
            "ISIN": isin,
            "M_K": round(m_k, 2),
            "M_D": round(m_d, 2),
            "W_K": round(w_k, 2),
            "W_D": round(w_d, 2),
            "D_K": round(d_k, 2),
            "D_D": round(d_d, 2),
            "STAGE": stage
        })

    except:
        continue

# -----------------------------------
# OUTPUT
# -----------------------------------

df_out = pd.DataFrame(results)

output_path = os.path.join(BASE_DIR, "data", "stochrsi_mtf_stage_dashboard.csv")
df_out.to_csv(output_path, index=False)

print("\n🔥 STOCHRSI STAGE DASHBOARD READY\n")
print(df_out.head(20))