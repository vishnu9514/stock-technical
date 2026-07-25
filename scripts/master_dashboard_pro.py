import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
mapping_file = os.path.join(BASE_DIR, "data", "industry_with_sector.csv")
industry_file = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")
prob_file = os.path.join(BASE_DIR, "data", "industry_cycle_probabilities_full.csv")

# -----------------------------------
# LOAD FILES
# -----------------------------------

mapping_df = pd.read_csv(mapping_file)
mapping_df["SYMBOL"] = mapping_df["symbol"].str.upper()

mapping_dict = mapping_df.set_index("SYMBOL")[["industry", "sector"]].to_dict("index")

industry = pd.read_csv(industry_file)
industry["DATE"] = pd.to_datetime(industry["DATE"])

latest_industry = industry.sort_values("DATE").groupby("MAIN_INDUSTRY").tail(1)
industry_phase_map = latest_industry.set_index("MAIN_INDUSTRY")["PHASE"].to_dict()

prob_df = pd.read_csv(prob_file)

# -----------------------------------
# PROCESS STOCKS
# -----------------------------------

rows = []

for file in os.listdir(data_folder):

    symbol = file.replace(".csv", "").upper()

    if symbol not in mapping_dict:
        continue

    df = pd.read_csv(os.path.join(data_folder, file))

    if "DATE" not in df.columns:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE")

    latest = df.iloc[-1]

    industry_name = mapping_dict[symbol]["industry"]
    sector = mapping_dict[symbol]["sector"]

    close = df["CLOSE"]

    # -----------------------------------
    # MULTI TIMEFRAME MOMENTUM
    # -----------------------------------

    daily = close.pct_change(5).iloc[-1]
    weekly = close.pct_change(20).iloc[-1]
    monthly = close.pct_change(60).iloc[-1]

    mtf_score = int(daily > 0) + int(weekly > 0) + int(monthly > 0)

    # -----------------------------------
    # BASIC SCORES
    # -----------------------------------

    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]

    price_score = int(latest["CLOSE"] > sma50) + int(latest["CLOSE"] > sma200)

    vol = df["VOLUME"]
    vol_avg20 = vol.rolling(20).mean().iloc[-1]

    volume_score = int(latest["VOLUME"] > vol_avg20)

    ret20 = close.pct_change(20).iloc[-1]
    momentum_score = int(ret20 > 0)

    # -----------------------------------
    # INDUSTRY PHASE
    # -----------------------------------

    phase = industry_phase_map.get(industry_name, "UNKNOWN")

    phase_score = {"ACCUMULATION": 3, "MARKUP": 4, "DISTRIBUTION": 1, "MARKDOWN": 0}.get(phase, 0)

    # -----------------------------------
    # PROBABILITY SCORE
    # -----------------------------------

    prob_row = prob_df[
        (prob_df["MAIN_INDUSTRY"] == industry_name) &
        (prob_df["PHASE"] == phase)
    ]

    prob_score = 0

    if not prob_row.empty and "MARKUP" in prob_row.columns:
        prob_score = prob_row.iloc[0]["MARKUP"]

    # -----------------------------------
    # FINAL SCORE
    # -----------------------------------

    final_score = (
        price_score +
        volume_score +
        momentum_score +
        mtf_score +
        phase_score +
        prob_score
    )

    rows.append({
        "STOCK": symbol,
        "SECTOR": sector,
        "INDUSTRY": industry_name,
        "PHASE": phase,
        "MTF_SCORE": mtf_score,
        "PROB_SCORE": prob_score,
        "FINAL_SCORE": final_score
    })

# -----------------------------------
# CREATE DASHBOARD
# -----------------------------------

df_dash = pd.DataFrame(rows)

# -----------------------------------
# LEADER RANKING
# -----------------------------------

df_dash["INDUSTRY_RANK"] = df_dash.groupby("INDUSTRY")["FINAL_SCORE"].rank(ascending=False)

# -----------------------------------
# SORT
# -----------------------------------

df_dash = df_dash.sort_values("FINAL_SCORE", ascending=False)

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "master_dashboard_pro.csv")
df_dash.to_csv(output_path, index=False)

print("\n🔥 MASTER PRO DASHBOARD READY")
print(df_dash.head(20))