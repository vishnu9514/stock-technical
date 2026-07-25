import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
mapping_file = os.path.join(BASE_DIR, "data", "industry_with_sector.csv")

# -----------------------------------
# LOAD MAPPING
# -----------------------------------

mapping_df = pd.read_csv(mapping_file)
mapping_df["SYMBOL"] = mapping_df["symbol"].str.upper()

mapping_dict = mapping_df.set_index("SYMBOL")["industry"].to_dict()

# -----------------------------------
# LOAD DATA
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
    df["MAIN_INDUSTRY"] = mapping_dict[symbol]

    all_data.append(df)

df_all = pd.concat(all_data, ignore_index=True)

df_all = df_all.sort_values(["MAIN_INDUSTRY", "DATE"])

print("✅ Data loaded:", len(df_all))

# -----------------------------------
# AGGREGATE INDUSTRY
# -----------------------------------

industry_df = df_all.groupby(["DATE", "MAIN_INDUSTRY"]).agg({
    "CLOSE": "mean",
    "VOLUME": "sum"
}).reset_index()

industry_df = industry_df.sort_values(["MAIN_INDUSTRY", "DATE"])

# -----------------------------------
# FEATURES
# -----------------------------------

industry_df["PRICE_MA20"] = industry_df.groupby("MAIN_INDUSTRY")["CLOSE"].transform(
    lambda x: x.rolling(20, min_periods=1).mean()
)

industry_df["PRICE_MA50"] = industry_df.groupby("MAIN_INDUSTRY")["CLOSE"].transform(
    lambda x: x.rolling(50, min_periods=1).mean()
)

industry_df["VOL_MA20"] = industry_df.groupby("MAIN_INDUSTRY")["VOLUME"].transform(
    lambda x: x.rolling(20, min_periods=1).mean()
)

industry_df["VOL_MA50"] = industry_df.groupby("MAIN_INDUSTRY")["VOLUME"].transform(
    lambda x: x.rolling(50, min_periods=1).mean()
)

# -----------------------------------
# CONDITIONS
# -----------------------------------

industry_df["PRICE_UP"] = industry_df["PRICE_MA20"] > industry_df["PRICE_MA50"]
industry_df["VOL_UP"] = industry_df["VOL_MA20"] > industry_df["VOL_MA50"]

# -----------------------------------
# PHASE
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

industry_df["PHASE"] = industry_df.apply(classify, axis=1)

# -----------------------------------
# SAVE FULL HISTORY
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")
industry_df.to_csv(output_path, index=False)

print("\n🔥 INDUSTRY PHASE HISTORY GENERATED")
print("Rows:", len(industry_df))