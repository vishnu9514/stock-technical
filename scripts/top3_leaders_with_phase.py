import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

dashboard_file = os.path.join(BASE_DIR, "data", "master_dashboard_main_industry.csv")

# -----------------------------------
# LOAD DASHBOARD
# -----------------------------------

df = pd.read_csv(dashboard_file)

# safety check
required_cols = ["STOCK", "MAIN_INDUSTRY", "PHASE", "FINAL_SCORE"]

for col in required_cols:
    if col not in df.columns:
        raise Exception(f"❌ Missing column: {col}")

# -----------------------------------
# SORT BY SCORE
# -----------------------------------

df = df.sort_values(["MAIN_INDUSTRY", "FINAL_SCORE"], ascending=[True, False])

# -----------------------------------
# PICK TOP 3 PER INDUSTRY
# -----------------------------------

top3 = df.groupby("MAIN_INDUSTRY").head(3)

# -----------------------------------
# CLEAN OUTPUT
# -----------------------------------

output = top3[[
    "MAIN_INDUSTRY",
    "STOCK",
    "PHASE",
    "FINAL_SCORE"
]]

# -----------------------------------
# SAVE
# -----------------------------------

output_path = os.path.join(BASE_DIR, "data", "top3_leaders_with_phase.csv")
output.to_csv(output_path, index=False)

print("\n🔥 TOP 3 LEADERS WITH PHASE GENERATED\n")
print(output.head(20))