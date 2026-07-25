import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
mapping_file = os.path.join(BASE_DIR, "data", "industry_with_sector.csv")

# -----------------------------------
# LOAD MAPPING
# -----------------------------------

mapping_df = pd.read_csv(mapping_file)

mapping_df["SYMBOL"] = mapping_df["symbol"].astype(str).str.upper().str.strip()
mapping_df["MAIN_INDUSTRY"] = mapping_df["industry"]

mapping_dict = mapping_df.set_index("SYMBOL")["MAIN_INDUSTRY"].to_dict()

# -----------------------------------
# LOAD STOCK DATA
# -----------------------------------

all_data = []

for file in os.listdir(data_folder):

    symbol = file.replace(".csv", "").upper()
    path = os.path.join(data_folder, file)

    if symbol not in mapping_dict:
        continue

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "DATE" not in df.columns:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df["STOCK"] = symbol
    df["MAIN_INDUSTRY"] = mapping_dict[symbol]

    all_data.append(df)

df_all = pd.concat(all_data, ignore_index=True)

df_all = df_all.sort_values(["STOCK", "DATE"])

# -----------------------------------
# PRICE STRENGTH
# -----------------------------------

df_all["SMA50"] = df_all.groupby("STOCK")["CLOSE"].transform(lambda x: x.rolling(50).mean())
df_all["SMA200"] = df_all.groupby("STOCK")["CLOSE"].transform(lambda x: x.rolling(200).mean())

df_all["PRICE_SCORE"] = (
    (df_all["CLOSE"] > df_all["SMA50"]).astype(int) +
    (df_all["CLOSE"] > df_all["SMA200"]).astype(int)
)

# -----------------------------------
# MOMENTUM
# -----------------------------------

df_all["RET_20"] = df_all.groupby("STOCK")["CLOSE"].pct_change(20)
df_all["MOM_SCORE"] = (df_all["RET_20"] > 0).astype(int)

# -----------------------------------
# VOLUME STRENGTH
# -----------------------------------

df_all["VOL_AVG20"] = df_all.groupby("STOCK")["VOLUME"].transform(lambda x: x.rolling(20).mean())
df_all["VOL_SCORE"] = (df_all["VOLUME"] > df_all["VOL_AVG20"]).astype(int)

# -----------------------------------
# TOTAL SCORE
# -----------------------------------

df_all["TOTAL_SCORE"] = (
    df_all["PRICE_SCORE"] +
    df_all["MOM_SCORE"] +
    df_all["VOL_SCORE"]
)

# -----------------------------------
# GET LATEST PER STOCK
# -----------------------------------

latest = df_all.sort_values("DATE").groupby("STOCK").tail(1)

# -----------------------------------
# FIND LEADERS
# -----------------------------------

leaders = (
    latest.sort_values("TOTAL_SCORE", ascending=False)
    .groupby("MAIN_INDUSTRY")
    .head(1)
)

# -----------------------------------
# OPTIONAL: TOP 3 PER INDUSTRY
# -----------------------------------

top3 = (
    latest.sort_values("TOTAL_SCORE", ascending=False)
    .groupby("MAIN_INDUSTRY")
    .head(3)
)

# -----------------------------------
# SAVE OUTPUT
# -----------------------------------

leaders.to_csv(os.path.join(BASE_DIR, "data", "main_industry_leaders.csv"), index=False)
top3.to_csv(os.path.join(BASE_DIR, "data", "main_industry_top3.csv"), index=False)

print("\n🔥 MAIN INDUSTRY LEADERS GENERATED")