import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

dashboard_file = os.path.join(BASE_DIR,"data","indicator_dashboard.csv")
output_file = os.path.join(BASE_DIR,"data","stochrsi_reversal_ranking.csv")

df = pd.read_csv(dashboard_file)

# previous momentum (approximate)
df["W_MOM"] = df["W_K"] - df["W_D"]
df["D_MOM"] = df["D_K"] - df["D_D"]

# reversal score
df["REVERSAL_SCORE"] = (
    (20 - df["3M_K"]).clip(lower=0) * 0.35 +
    (20 - df["M_K"]).clip(lower=0) * 0.30 +
    df["W_MOM"] * 0.20 +
    df["D_MOM"] * 0.15
)

# filter oversold candidates
rev = df[
    (df["3M_K"] < 35) &
    (df["M_K"] < 30)
]

rev = rev.sort_values("REVERSAL_SCORE",ascending=False)

rev["RANK"] = range(1,len(rev)+1)

rev.to_csv(output_file,index=False)

print("Reversal ranking created:",output_file)