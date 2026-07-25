import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

# -----------------------------------
# LOAD ALL STOCK DATA
# -----------------------------------

all_data = []

for file in os.listdir(data_folder):

    path = os.path.join(data_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "DATE" not in df.columns:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"])
    df["STOCK"] = file.replace(".csv", "")

    all_data.append(df)

# combine all stocks
df_all = pd.concat(all_data, ignore_index=True)

print("✅ Data Loaded:", len(df_all))

# -----------------------------------
# CALCULATE RETURNS
# -----------------------------------

df_all = df_all.sort_values(["STOCK", "DATE"])

df_all["RETURN"] = df_all.groupby("STOCK")["CLOSE"].pct_change()

# -----------------------------------
# INDUSTRY CYCLE
# -----------------------------------

industry_cycle = (
    df_all.groupby(["DATE", "INDUSTRY"])["RETURN"]
    .mean()
    .reset_index()
)

# -----------------------------------
# SECTOR CYCLE
# -----------------------------------

sector_cycle = (
    df_all.groupby(["DATE", "SECTOR"])["RETURN"]
    .mean()
    .reset_index()
)

# -----------------------------------
# MOMENTUM (ROLLING)
# -----------------------------------

industry_cycle["MOMENTUM"] = (
    industry_cycle.groupby("INDUSTRY")["RETURN"]
    .rolling(20)
    .mean()
    .reset_index(drop=True)
)

sector_cycle["MOMENTUM"] = (
    sector_cycle.groupby("SECTOR")["RETURN"]
    .rolling(20)
    .mean()
    .reset_index(drop=True)
)

# -----------------------------------
# RANKING
# -----------------------------------

latest_date = df_all["DATE"].max()

latest_industry = industry_cycle[industry_cycle["DATE"] == latest_date]
latest_sector = sector_cycle[sector_cycle["DATE"] == latest_date]

latest_industry = latest_industry.sort_values("MOMENTUM", ascending=False)
latest_sector = latest_sector.sort_values("MOMENTUM", ascending=False)

# -----------------------------------
# SAVE OUTPUT
# -----------------------------------

latest_industry.to_csv(os.path.join(BASE_DIR, "data", "industry_cycle.csv"), index=False)
latest_sector.to_csv(os.path.join(BASE_DIR, "data", "sector_cycle.csv"), index=False)

print("\n🔥 INDUSTRY & SECTOR CYCLE GENERATED")