import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
mapping_file = os.path.join(BASE_DIR, "data", "industry_with_sector.csv")
industry_file = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")

# -----------------------------------
# LOAD MAPPING
# -----------------------------------

mapping_df = pd.read_csv(mapping_file)
mapping_df["SYMBOL"] = mapping_df["symbol"].str.upper()

mapping_dict = mapping_df.set_index("SYMBOL")[["industry", "sector"]].to_dict("index")

# -----------------------------------
# LOAD INDUSTRY PHASE (LATEST)
# -----------------------------------

industry = pd.read_csv(industry_file)
industry["DATE"] = pd.to_datetime(industry["DATE"])

latest_industry = industry.sort_values("DATE").groupby("MAIN_INDUSTRY").tail(1)

industry_phase_map = latest_industry.set_index("MAIN_INDUSTRY")["PHASE"].to_dict()

# -----------------------------------
# LOAD STOCK DATA
# -----------------------------------

rows = []

for file in os.listdir(data_folder):

    symbol = file.replace(".csv", "").upper()

    if symbol not in mapping_dict:
        continue

    path = os.path.join(data_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "DATE" not in df.columns:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE")

    latest = df.iloc[-1]

    industry_name = mapping_dict[symbol]["industry"]
    sector = mapping_dict[symbol]["sector"]

    # -----------------------------------
    # FEATURES
    # -----------------------------------

    close = df["CLOSE"]

    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]

    price_score = int(latest["CLOSE"] > sma50) + int(latest["CLOSE"] > sma200)

    ret20 = close.pct_change(20).iloc[-1]
    momentum_score = int(ret20 > 0)

    vol = df["VOLUME"]
    vol_avg20 = vol.rolling(20).mean().iloc[-1]
    volume_score = int(latest["VOLUME"] > vol_avg20)

    # volatility compression
    vol_std = close.rolling(20).std().iloc[-1]
    vol_std_avg = close.rolling(50).std().mean()

    volatility_score = int(vol_std < vol_std_avg)

    # -----------------------------------
    # INDUSTRY PHASE SCORE
    # -----------------------------------

    phase = industry_phase_map.get(industry_name, "UNKNOWN")

    phase_score = 0

    if phase == "ACCUMULATION":
        phase_score = 2
    elif phase == "MARKUP":
        phase_score = 3
    elif phase == "DISTRIBUTION":
        phase_score = 1
    else:
        phase_score = 0

    # -----------------------------------
    # FINAL SCORE
    # -----------------------------------

    total_score = (
        price_score +
        momentum_score +
        volume_score +
        volatility_score +
        phase_score
    )

    rows.append({
        "STOCK": symbol,
        "SECTOR": sector,
        "INDUSTRY": industry_name,
        "PHASE": phase,
        "PRICE_SCORE": price_score,
        "MOMENTUM": momentum_score,
        "VOLUME": volume_score,
        "VOLATILITY": volatility_score,
        "FINAL_SCORE": total_score
    })

# -----------------------------------
# CREATE DASHBOARD
# -----------------------------------

dashboard = pd.DataFrame(rows)

dashboard = dashboard.sort_values("FINAL_SCORE", ascending=False)

# -----------------------------------
# SAVE
# -----------------------------------

dashboard.to_csv(os.path.join(BASE_DIR, "data", "master_dashboard.csv"), index=False)

print("\n🔥 MASTER DASHBOARD READY")
print(dashboard.head(20))