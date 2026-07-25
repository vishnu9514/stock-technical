import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

all_data = []

# -----------------------------------
# LOAD DATA
# -----------------------------------

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

df_all = pd.concat(all_data, ignore_index=True)

# -----------------------------------
# SORT
# -----------------------------------

df_all = df_all.sort_values(["STOCK", "DATE"])

# -----------------------------------
# PRICE MOMENTUM
# -----------------------------------

df_all["SMA50"] = df_all.groupby("STOCK")["CLOSE"].transform(lambda x: x.rolling(50).mean())
df_all["SMA200"] = df_all.groupby("STOCK")["CLOSE"].transform(lambda x: x.rolling(200).mean())

df_all["PRICE_MOMENTUM"] = (
    (df_all["CLOSE"] > df_all["SMA50"]) &
    (df_all["CLOSE"] > df_all["SMA200"])
)

# -----------------------------------
# VOLUME MOMENTUM
# -----------------------------------

df_all["VOL_AVG20"] = df_all.groupby("STOCK")["VOLUME"].transform(lambda x: x.rolling(20).mean())

df_all["VOLUME_MOMENTUM"] = df_all["VOLUME"] > df_all["VOL_AVG20"]

# -----------------------------------
# INDUSTRY / SECTOR CYCLE
# -----------------------------------

df_all["RETURN"] = df_all.groupby("STOCK")["CLOSE"].pct_change()

industry_strength = (
    df_all.groupby(["DATE", "INDUSTRY"])["RETURN"]
    .mean()
    .reset_index()
)

sector_strength = (
    df_all.groupby(["DATE", "SECTOR"])["RETURN"]
    .mean()
    .reset_index()
)

# rolling momentum
industry_strength["IND_MOM"] = (
    industry_strength.groupby("INDUSTRY")["RETURN"]
    .rolling(10)
    .mean()
    .reset_index(drop=True)
)

sector_strength["SEC_MOM"] = (
    sector_strength.groupby("SECTOR")["RETURN"]
    .rolling(10)
    .mean()
    .reset_index(drop=True)
)

# -----------------------------------
# MERGE BACK
# -----------------------------------

df_all = df_all.merge(industry_strength, on=["DATE", "INDUSTRY"], how="left")
df_all = df_all.merge(sector_strength, on=["DATE", "SECTOR"], how="left")

# -----------------------------------
# FINAL FILTER
# -----------------------------------

latest_date = df_all["DATE"].max()

latest = df_all[df_all["DATE"] == latest_date]

filtered = latest[
    (latest["IND_MOM"] > 0) &
    (latest["SEC_MOM"] > 0) &
    (latest["PRICE_MOMENTUM"]) &
    (latest["VOLUME_MOMENTUM"])
]

# -----------------------------------
# RANKING
# -----------------------------------

filtered = filtered.sort_values(
    ["IND_MOM", "SEC_MOM"],
    ascending=False
)

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "top_cycle_stocks.csv")
filtered.to_csv(output_path, index=False)

print("\n🔥 TOP CYCLE STOCKS GENERATED")