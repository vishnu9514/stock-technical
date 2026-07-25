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
mapping_dict = mapping_df.set_index("SYMBOL")["industry"].to_dict()

# -----------------------------------
# LOAD STOCK DATA
# -----------------------------------

all_data = []

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

    df["STOCK"] = symbol
    df["MAIN_INDUSTRY"] = mapping_dict[symbol]

    all_data.append(df)

df_all = pd.concat(all_data, ignore_index=True)

print("✅ Data loaded:", len(df_all))

# -----------------------------------
# FEATURES
# -----------------------------------

df_all["RET_20"] = df_all.groupby("STOCK")["CLOSE"].pct_change(20)

df_all["VOL_AVG20"] = df_all.groupby("STOCK")["VOLUME"].transform(
    lambda x: x.rolling(20, min_periods=1).mean()
)

df_all["VOL_SCORE"] = (df_all["VOLUME"] > df_all["VOL_AVG20"]).astype(int)
df_all["MOM_SCORE"] = (df_all["RET_20"] > 0).astype(int)

df_all["TOTAL_SCORE"] = df_all["VOL_SCORE"] + df_all["MOM_SCORE"]

# -----------------------------------
# DAILY LEADER PER INDUSTRY
# -----------------------------------

leaders = (
    df_all.sort_values("TOTAL_SCORE", ascending=False)
    .groupby(["DATE", "MAIN_INDUSTRY"])
    .head(1)
)

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "historical_leaders.csv")
leaders.to_csv(output_path, index=False)

print("\n🔥 HISTORICAL LEADERS GENERATED")
print("Rows:", len(leaders))