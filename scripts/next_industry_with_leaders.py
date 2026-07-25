import pandas as pd
import os

# -----------------------------------
# BASE PATH
# -----------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

industry_file = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")
dashboard_file = os.path.join(BASE_DIR, "data", "master_dashboard_pro.csv")

# -----------------------------------
# CHECK FILES
# -----------------------------------

if not os.path.exists(industry_file):
    raise Exception("❌ main_industry_dashboard_full.csv not found")

if not os.path.exists(dashboard_file):
    raise Exception("❌ master_dashboard_pro.csv not found → Run pipeline first")

print("✅ Using dashboard:", dashboard_file)

# -----------------------------------
# LOAD DATA
# -----------------------------------

industry_df = pd.read_csv(industry_file)
industry_df["DATE"] = pd.to_datetime(industry_df["DATE"])

dash_df = pd.read_csv(dashboard_file)

# -----------------------------------
# SORT DATA
# -----------------------------------

industry_df = industry_df.sort_values(["MAIN_INDUSTRY", "DATE"])

# -----------------------------------
# 🔥 CREATE FEATURES (AUTO FIX)
# -----------------------------------

industry_df["RETURN_20"] = industry_df.groupby("MAIN_INDUSTRY")["CLOSE"].pct_change(20)

industry_df["VOL_20"] = (
    industry_df.groupby("MAIN_INDUSTRY")["VOLUME"]
    .rolling(20).mean().reset_index(level=0, drop=True)
)

industry_df["VOL_50"] = (
    industry_df.groupby("MAIN_INDUSTRY")["VOLUME"]
    .rolling(50).mean().reset_index(level=0, drop=True)
)

industry_df["VOLATILITY_20"] = (
    industry_df.groupby("MAIN_INDUSTRY")["CLOSE"]
    .rolling(20).std().reset_index(level=0, drop=True)
)

# -----------------------------------
# GET LATEST INDUSTRY DATA
# -----------------------------------

latest_ind = industry_df.groupby("MAIN_INDUSTRY").tail(1)

# -----------------------------------
# NEXT INDUSTRY SCORING
# -----------------------------------

scores = []

for _, row in latest_ind.iterrows():

    score = 0

    if pd.notna(row["RETURN_20"]) and -0.05 < row["RETURN_20"] < 0.05:
        score += 2

    if pd.notna(row["VOL_20"]) and pd.notna(row["VOL_50"]) and row["VOL_20"] > row["VOL_50"]:
        score += 2

    if pd.notna(row["VOLATILITY_20"]) and row["VOLATILITY_20"] < latest_ind["VOLATILITY_20"].mean():
        score += 2

    if pd.notna(row["RETURN_20"]) and 0 < row["RETURN_20"] < 0.10:
        score += 1

    scores.append(score)

latest_ind["NEXT_SCORE"] = scores

# -----------------------------------
# FILTER INDUSTRIES
# -----------------------------------

if "PHASE" in latest_ind.columns:
    candidates = latest_ind[latest_ind["PHASE"] == "ACCUMULATION"]
else:
    print("⚠️ No PHASE column → using all industries")
    candidates = latest_ind

if candidates.empty:
    print("⚠️ No ACCUMULATION industries → fallback to all")
    candidates = latest_ind

candidates = candidates.sort_values("NEXT_SCORE", ascending=False)

top_industries = candidates.head(5)["MAIN_INDUSTRY"].tolist()

print("\n🔥 TOP NEXT INDUSTRIES:", top_industries)

# -----------------------------------
# AUTO DETECT INDUSTRY COLUMN (DASHBOARD)
# -----------------------------------

possible_cols = ["MAIN_INDUSTRY", "INDUSTRY", "industry"]

industry_col = None

for col in possible_cols:
    if col in dash_df.columns:
        industry_col = col
        break

if industry_col is None:
    raise Exception(f"❌ No industry column found in dashboard: {dash_df.columns}")

print("✅ Using dashboard column:", industry_col)

# -----------------------------------
# FIND TOP 3 LEADERS
# -----------------------------------

leaders_list = []

for ind in top_industries:

    sub = dash_df[dash_df[industry_col] == ind]

    if sub.empty:
        continue

    top3 = sub.sort_values("FINAL_SCORE", ascending=False).head(3)

    for rank, (_, row) in enumerate(top3.iterrows(), start=1):

        leaders_list.append({
            "MAIN_INDUSTRY": ind,
            "STOCK": row["STOCK"],
            "FINAL_SCORE": row["FINAL_SCORE"],
            "RANK": rank,
            "NEXT_SCORE": candidates.loc[
                candidates["MAIN_INDUSTRY"] == ind, "NEXT_SCORE"
            ].values[0]
        })

# -----------------------------------
# OUTPUT
# -----------------------------------

final = pd.DataFrame(leaders_list)

if final.empty:
    print("❌ No leaders found")
    exit()

output_path = os.path.join(BASE_DIR, "data", "next_industry_with_leaders.csv")
final.to_csv(output_path, index=False)

print("\n🔥 NEXT INDUSTRY + LEADERS GENERATED\n")
print(final.head(20))