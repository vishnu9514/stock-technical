import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

stocks_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
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
# RSI FUNCTION
# -----------------------------------

def compute_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

# -----------------------------------
# STOCH RSI (TradingView Style)
# -----------------------------------

def compute_stochrsi(close):

    rsi = compute_rsi(close, 14)

    min_rsi = rsi.rolling(14).min()
    max_rsi = rsi.rolling(14).max()

    stoch = (rsi - min_rsi) / (max_rsi - min_rsi)

    k = stoch.rolling(3).mean() * 100
    d = k.rolling(3).mean()

    return k, d

# -----------------------------------
# RESAMPLE FUNCTION
# -----------------------------------

def resample_df(df, freq):
    return df.resample(freq).agg({
        "OPEN": "first",
        "HIGH": "max",
        "LOW": "min",
        "CLOSE": "last",
        "VOLUME": "sum"
    }).dropna()

# -----------------------------------
# PROCESS ALL STOCKS
# -----------------------------------

results = []

for file in os.listdir(stocks_folder):

    path = os.path.join(stocks_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "DATE" not in df.columns:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE").set_index("DATE")

    symbol = file.replace(".csv", "").upper()
    isin = isin_map.get(symbol, "UNKNOWN")

    try:
        # DAILY
        k_d, d_d = compute_stochrsi(df["CLOSE"])

        # WEEKLY
        w = resample_df(df, "W")
        k_w, d_w = compute_stochrsi(w["CLOSE"])

        # MONTHLY (ME fix)
        m = resample_df(df, "ME")
        k_m, d_m = compute_stochrsi(m["CLOSE"])

        # QUARTERLY (3M)
        q = resample_df(df, "QE")
        k_q, d_q = compute_stochrsi(q["CLOSE"])

        # latest values
        row = {
            "STOCK": symbol,
            "ISIN": isin,

            "K_D": k_d.iloc[-1],
            "D_D": d_d.iloc[-1],

            "K_W": k_w.iloc[-1],
            "D_W": d_w.iloc[-1],

            "K_M": k_m.iloc[-1],
            "D_M": d_m.iloc[-1],

            "K_3M": k_q.iloc[-1],
            "D_3M": d_q.iloc[-1],
        }

        results.append(row)

    except:
        continue

# -----------------------------------
# CREATE DASHBOARD
# -----------------------------------

df_out = pd.DataFrame(results)

# -----------------------------------
# FILTER (BELOW 30)
# -----------------------------------

condition = (
    (df_out["K_D"] < 30) |
    (df_out["K_W"] < 30) |
    (df_out["K_M"] < 30) |
    (df_out["K_3M"] < 30)
)

df_out = df_out[condition]

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "stochrsi_multi_tf_dashboard.csv")
df_out.to_csv(output_path, index=False)

print("\n🔥 STOCHRSI DASHBOARD GENERATED\n")
print(df_out.head(20))