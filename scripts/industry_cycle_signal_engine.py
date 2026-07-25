import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

industry_file = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")

# -----------------------------------
# LOAD DATA
# -----------------------------------

df = pd.read_csv(industry_file)
df["DATE"] = pd.to_datetime(df["DATE"])

df = df.sort_values(["MAIN_INDUSTRY", "DATE"])

# -----------------------------------
# NEXT PHASE
# -----------------------------------

df["NEXT_PHASE"] = df.groupby("MAIN_INDUSTRY")["PHASE"].shift(-1)
df = df.dropna(subset=["NEXT_PHASE"])

# -----------------------------------
# PROBABILITY TABLE
# -----------------------------------

prob_list = []

for ind in df["MAIN_INDUSTRY"].unique():

    sub = df[df["MAIN_INDUSTRY"] == ind]

    trans = pd.crosstab(
        sub["PHASE"],
        sub["NEXT_PHASE"],
        normalize="index"
    )

    trans["MAIN_INDUSTRY"] = ind
    trans = trans.reset_index()

    prob_list.append(trans)

prob_df = pd.concat(prob_list, ignore_index=True)

# -----------------------------------
# GET LATEST STATE (WITH DATE)
# -----------------------------------

latest = df.sort_values("DATE").groupby("MAIN_INDUSTRY").tail(1)

# -----------------------------------
# MERGE CURRENT + PROBABILITY
# -----------------------------------

final = latest.merge(
    prob_df,
    left_on=["MAIN_INDUSTRY", "PHASE"],
    right_on=["MAIN_INDUSTRY", "PHASE"],
    how="left"
)

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "industry_cycle_signal.csv")
final.to_csv(output_path, index=False)

print("\n🔥 INDUSTRY CYCLE SIGNAL WITH DATE GENERATED")