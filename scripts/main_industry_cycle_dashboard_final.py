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
mapping_df["SECTOR"] = mapping_df["sector"]

mapping_dict = mapping_df.set_index("SYMBOL")[["MAIN_INDUSTRY", "SECTOR"]].to_dict("index")

print(f"✅ Total mapped industries: {mapping_df['industry'].nunique()}")

# -----------------------------------
# LOAD STOCK DATA
# -----------------------------------

all_data = []

for file in os.listdir(data_folder):

    symbol = file.replace(".csv", "").upper()
    path = os.path.join(data_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "DATE" not in df.columns:
        continue

    if symbol not in mapping_dict:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df["MAIN_INDUSTRY"] = mapping_dict[symbol]["MAIN_INDUSTRY"]
    df["SECTOR"] = mapping_dict[symbol]["SECTOR"]
    df["STOCK"] = symbol

    all_data.append(df)

df_all = pd.concat(all_data, ignore_index=True)

df_all = df_all.sort_values(["STOCK", "DATE"])

print("✅ Total records loaded:", len(df_all))

# -----------------------------------
# AGGREGATE MAIN INDUSTRY
# -----------------------------------

main_industry_df = df_all.groupby(["DATE", "MAIN_INDUSTRY"]).agg({
    "CLOSE": "mean",
    "VOLUME": "sum"
}).reset_index()

main_industry_df = main_industry_df.sort_values(["MAIN_INDUSTRY", "DATE"])

# -----------------------------------
# FEATURE ENGINEERING (FIXED)
# -----------------------------------

main_industry_df["PRICE_MA20"] = main_industry_df.groupby("MAIN_INDUSTRY")["CLOSE"].transform(
    lambda x: x.rolling(20, min_periods=1).mean()
)

main_industry_df["PRICE_MA50"] = main_industry_df.groupby("MAIN_INDUSTRY")["CLOSE"].transform(
    lambda x: x.rolling(50, min_periods=1).mean()
)

main_industry_df["VOL_MA20"] = main_industry_df.groupby("MAIN_INDUSTRY")["VOLUME"].transform(
    lambda x: x.rolling(20, min_periods=1).mean()
)

main_industry_df["VOL_MA50"] = main_industry_df.groupby("MAIN_INDUSTRY")["VOLUME"].transform(
    lambda x: x.rolling(50, min_periods=1).mean()
)

# -----------------------------------
# CONDITIONS
# -----------------------------------

main_industry_df["PRICE_UP"] = main_industry_df["PRICE_MA20"] > main_industry_df["PRICE_MA50"]
main_industry_df["VOL_UP"] = main_industry_df["VOL_MA20"] > main_industry_df["VOL_MA50"]

# -----------------------------------
# PHASE CLASSIFICATION
# -----------------------------------

def classify(row):
    if (not row["PRICE_UP"]) and row["VOL_UP"]:
        return "ACCUMULATION"
    elif row["PRICE_UP"] and row["VOL_UP"]:
        return "MARKUP"
    elif (not row["PRICE_UP"]) and (not row["VOL_UP"]):
        return "MARKDOWN"
    else:
        return "DISTRIBUTION"

main_industry_df["PHASE"] = main_industry_df.apply(classify, axis=1)

# -----------------------------------
# CYCLE DETECTION
# -----------------------------------

main_industry_df["PREV_PHASE"] = main_industry_df.groupby("MAIN_INDUSTRY")["PHASE"].shift(1)
main_industry_df["NEW_CYCLE"] = main_industry_df["PHASE"] != main_industry_df["PREV_PHASE"]

cycle_count = main_industry_df.groupby("MAIN_INDUSTRY")["NEW_CYCLE"].sum().reset_index()
cycle_count.columns = ["MAIN_INDUSTRY", "CYCLE_COUNT"]

# -----------------------------------
# ✅ FIX: LATEST PER INDUSTRY
# -----------------------------------

latest = main_industry_df.sort_values("DATE").groupby("MAIN_INDUSTRY").tail(1)

# -----------------------------------
# MERGE DASHBOARD
# -----------------------------------

dashboard = latest.merge(cycle_count, on="MAIN_INDUSTRY")

# -----------------------------------
# OPTIONAL: ADD STRENGTH
# -----------------------------------

main_industry_df["RETURN"] = main_industry_df.groupby("MAIN_INDUSTRY")["CLOSE"].pct_change()

strength = main_industry_df.groupby("MAIN_INDUSTRY")["RETURN"].mean().reset_index()
strength.columns = ["MAIN_INDUSTRY", "AVG_RETURN"]

dashboard = dashboard.merge(strength, on="MAIN_INDUSTRY", how="left")

# -----------------------------------
# RANKING
# -----------------------------------

dashboard = dashboard.sort_values(
    ["PHASE", "AVG_RETURN"],
    ascending=[True, False]
)

# -----------------------------------
# DEBUG: CHECK MISSING INDUSTRIES
# -----------------------------------

all_industries = set(mapping_df["industry"].unique())
present_industries = set(dashboard["MAIN_INDUSTRY"].unique())

missing = all_industries - present_industries

print("\n📊 Missing industries:", len(missing))

# -----------------------------------
# SAVE OUTPUT
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "main_industry_dashboard.csv")
dashboard.to_csv(output_path, index=False)

print("\n🔥 MAIN INDUSTRY DASHBOARD READY (FULL VERSION)")