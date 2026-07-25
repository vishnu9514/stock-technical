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

df_all = df_all.sort_values(["STOCK", "DATE"])

# -----------------------------------
# PRICE MOMENTUM
# -----------------------------------

df_all["SMA50"] = df_all.groupby("STOCK")["CLOSE"].transform(lambda x: x.rolling(50).mean())
df_all["SMA200"] = df_all.groupby("STOCK")["CLOSE"].transform(lambda x: x.rolling(200).mean())

df_all["PRICE_SCORE"] = (
    (df_all["CLOSE"] > df_all["SMA50"]).astype(int) +
    (df_all["CLOSE"] > df_all["SMA200"]).astype(int)
)

# -----------------------------------
# RETURNS
# -----------------------------------

df_all["RET_20"] = df_all.groupby("STOCK")["CLOSE"].pct_change(20)

# -----------------------------------
# VOLUME STRENGTH
# -----------------------------------

df_all["VOL_AVG20"] = df_all.groupby("STOCK")["VOLUME"].transform(lambda x: x.rolling(20).mean())
df_all["VOL_SCORE"] = (df_all["VOLUME"] > df_all["VOL_AVG20"]).astype(int)

# -----------------------------------
# FINAL SCORE
# -----------------------------------

df_all["TOTAL_SCORE"] = (
    df_all["PRICE_SCORE"] +
    df_all["VOL_SCORE"] +
    (df_all["RET_20"] > 0).astype(int)
)

# -----------------------------------
# GET LATEST DATA
# -----------------------------------

latest_date = df_all["DATE"].max()
latest = df_all[df_all["DATE"] == latest_date]

# -----------------------------------
# FIND LEADERS
# -----------------------------------

leaders = (
    latest.sort_values("TOTAL_SCORE", ascending=False)
    .groupby("INDUSTRY")
    .head(1)
)

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "industry_leaders.csv")
leaders.to_csv(output_path, index=False)

print("\n🔥 INDUSTRY LEADERS GENERATED")