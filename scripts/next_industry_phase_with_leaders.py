import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
industry_file = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")
leader_file = os.path.join(BASE_DIR, "data", "master_dashboard_pro.csv")
output_file = os.path.join(BASE_DIR, "data", "next_industry_phase_with_leaders.csv")

required_files = {
    "industry phase history": industry_file,
    "leader dashboard": leader_file,
}

for name, path in required_files.items():
    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ Required file not found: {name} ({path})")

# -----------------------------------
# LOAD INDUSTRY PHASE HISTORY
# -----------------------------------
industry_df = pd.read_csv(industry_file)
industry_df["DATE"] = pd.to_datetime(industry_df["DATE"], errors="coerce")
industry_df = industry_df.sort_values(["MAIN_INDUSTRY", "DATE"]).reset_index(drop=True)

industry_df["NEXT_PHASE"] = industry_df.groupby("MAIN_INDUSTRY")["PHASE"].shift(-1)
industry_df["PREV_PHASE"] = industry_df.groupby("MAIN_INDUSTRY")["PHASE"].shift(1)

# -----------------------------------
# LATEST INDUSTRY STATE
# -----------------------------------
latest = industry_df.groupby("MAIN_INDUSTRY").tail(1).copy()
latest = latest.reset_index(drop=True)
latest["NEW_CYCLE"] = latest["PHASE"] != latest["PREV_PHASE"]

# -----------------------------------
# TRANSITION PROBABILITIES
# -----------------------------------
phase_probs = []
for industry_name, sub in industry_df.groupby("MAIN_INDUSTRY"):
    trans = pd.crosstab(
        sub["PHASE"],
        sub["NEXT_PHASE"],
        normalize="index"
    ).reset_index()
    trans["MAIN_INDUSTRY"] = industry_name
    phase_probs.append(trans)

prob_df = pd.concat(phase_probs, ignore_index=True, sort=False).fillna(0.0)

phase_columns = ["ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN"]
for col in phase_columns:
    if col not in prob_df.columns:
        prob_df[col] = 0.0

prob_df["PREDICTED_NEXT_PHASE"] = prob_df[phase_columns].idxmax(axis=1)
prob_df = prob_df[["MAIN_INDUSTRY", "PHASE"] + phase_columns + ["PREDICTED_NEXT_PHASE"]]

# -----------------------------------
# MERGE NEXT-PHASE PROBABILITIES
# -----------------------------------
merged = latest.merge(
    prob_df,
    left_on=["MAIN_INDUSTRY", "PHASE"],
    right_on=["MAIN_INDUSTRY", "PHASE"],
    how="left"
)

# -----------------------------------
# LOAD LEADERS
# -----------------------------------
leaders_df = pd.read_csv(leader_file)
if "MAIN_INDUSTRY" not in leaders_df.columns:
    if "INDUSTRY" in leaders_df.columns:
        leaders_df = leaders_df.rename(columns={"INDUSTRY": "MAIN_INDUSTRY"})
    else:
        raise Exception("❌ master dashboard missing MAIN_INDUSTRY or INDUSTRY column")

leaders_df = leaders_df.sort_values(["MAIN_INDUSTRY", "FINAL_SCORE"], ascending=[True, False])

leader_rows = []
for industry_name, sub in leaders_df.groupby("MAIN_INDUSTRY"):
    top_stocks = sub.head(3).reset_index(drop=True)
    row = {"MAIN_INDUSTRY": industry_name}
    for rank in range(1, 4):
        if rank - 1 < len(top_stocks):
            row[f"LEADER_{rank}"] = top_stocks.loc[rank - 1, "STOCK"]
            row[f"LEADER_{rank}_SCORE"] = top_stocks.loc[rank - 1, "FINAL_SCORE"]
        else:
            row[f"LEADER_{rank}"] = ""
            row[f"LEADER_{rank}_SCORE"] = 0
    leader_rows.append(row)

leaders_summary = pd.DataFrame(leader_rows)

output_df = merged.merge(
    leaders_summary,
    on="MAIN_INDUSTRY",
    how="left"
)

output_columns = [
    "MAIN_INDUSTRY",
    "DATE",
    "PHASE",
    "PREV_PHASE",
    "NEW_CYCLE",
    "PREDICTED_NEXT_PHASE",
    "ACCUMULATION",
    "MARKUP",
    "DISTRIBUTION",
    "MARKDOWN",
    "LEADER_1",
    "LEADER_1_SCORE",
    "LEADER_2",
    "LEADER_2_SCORE",
    "LEADER_3",
    "LEADER_3_SCORE",
]

output_df = output_df[output_columns]

output_df.to_csv(output_file, index=False)

print("\n🔥 NEXT INDUSTRY PHASE + LEADERS GENERATED")
print(f"✅ Output saved to: {output_file}")
print(output_df.head(20).to_string(index=False))
