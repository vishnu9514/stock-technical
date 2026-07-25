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
# CALCULATE PER INDUSTRY
# -----------------------------------

results = []

for industry in df["MAIN_INDUSTRY"].unique():

    sub = df[df["MAIN_INDUSTRY"] == industry]

    transition = pd.crosstab(
        sub["PHASE"],
        sub["NEXT_PHASE"],
        normalize="index"
    )

    transition["MAIN_INDUSTRY"] = industry

    transition = transition.reset_index()

    results.append(transition)

# -----------------------------------
# COMBINE
# -----------------------------------

final_df = pd.concat(results, ignore_index=True)

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "industry_cycle_probabilities_full.csv")
final_df.to_csv(output_path, index=False)

print("\n🔥 INDUSTRY-WISE CYCLE PROBABILITIES GENERATED")
print("Rows:", len(final_df))