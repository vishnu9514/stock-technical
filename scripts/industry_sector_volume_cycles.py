import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

all_data = []

# -----------------------------------
# LOAD ALL STOCKS
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

df_all = df_all.sort_values(["STOCK", "DATE"])

# -----------------------------------
# CALCULATE RETURNS
# -----------------------------------

df_all["RETURN"] = df_all.groupby("STOCK")["CLOSE"].pct_change()

# -----------------------------------
# INDUSTRY AGGREGATION
# -----------------------------------

industry_df = df_all.groupby(["DATE", "INDUSTRY"]).agg({
    "CLOSE": "mean",
    "VOLUME": "sum",
    "RETURN": "mean"
}).reset_index()

# -----------------------------------
# SECTOR AGGREGATION
# -----------------------------------

sector_df = df_all.groupby(["DATE", "SECTOR"]).agg({
    "CLOSE": "mean",
    "VOLUME": "sum",
    "RETURN": "mean"
}).reset_index()

# -----------------------------------
# FUNCTION TO DETECT CYCLE
# -----------------------------------

def detect_cycle(df, group_col):

    df = df.sort_values([group_col, "DATE"])

    df["VOL_AVG20"] = df.groupby(group_col)["VOLUME"].transform(lambda x: x.rolling(20).mean())
    df["VOL_AVG50"] = df.groupby(group_col)["VOLUME"].transform(lambda x: x.rolling(50).mean())

    df["VOL_TREND_UP"] = df["VOL_AVG20"] > df["VOL_AVG50"]
    df["VOL_SPIKE"] = df["VOLUME"] > (1.5 * df["VOL_AVG20"])

    df["PRICE_UP"] = df.groupby(group_col)["CLOSE"].transform(lambda x: x > x.rolling(20).mean())

    latest = df.groupby(group_col).tail(1)

    cycles = []

    for _, row in latest.iterrows():

        if (not row["PRICE_UP"]) and row["VOL_TREND_UP"]:
            cycle = "ACCUMULATION"

        elif row["PRICE_UP"] and row["VOL_SPIKE"]:
            cycle = "EXPANSION"

        elif (not row["PRICE_UP"]) and row["VOL_SPIKE"]:
            cycle = "DISTRIBUTION"

        else:
            cycle = "DECLINE"

        cycles.append({
            group_col: row[group_col],
            "CYCLE": cycle,
            "PRICE": row["CLOSE"],
            "VOLUME": row["VOLUME"]
        })

    return pd.DataFrame(cycles)

# -----------------------------------
# APPLY
# -----------------------------------

industry_cycles = detect_cycle(industry_df, "INDUSTRY")
sector_cycles = detect_cycle(sector_df, "SECTOR")

# -----------------------------------
# SAVE
# -----------------------------------

industry_cycles.to_csv(os.path.join(BASE_DIR, "data", "industry_volume_cycles.csv"), index=False)
sector_cycles.to_csv(os.path.join(BASE_DIR, "data", "sector_volume_cycles.csv"), index=False)

print("\n🔥 INDUSTRY & SECTOR VOLUME CYCLES READY")