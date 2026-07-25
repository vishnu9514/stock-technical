import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

dashboard_file = os.path.join(BASE_DIR,"data","indicator_dashboard.csv")

output_file = os.path.join(BASE_DIR,"data","nse_momentum_ranking.csv")

print("Loading dashboard...")

df = pd.read_csv(dashboard_file)

# calculate weighted momentum score

df["MOMENTUM_SCORE"] = (
    df["3M_K"] * 0.40 +
    df["M_K"] * 0.30 +
    df["W_K"] * 0.20 +
    df["D_K"] * 0.10
)

# rank stocks

df = df.sort_values("MOMENTUM_SCORE",ascending=False)

df["RANK"] = range(1,len(df)+1)

# optional classification

df["TREND"] = "Neutral"

df.loc[df["MOMENTUM_SCORE"] > 70,"TREND"] = "Strong Bullish"
df.loc[(df["MOMENTUM_SCORE"] > 50) & (df["MOMENTUM_SCORE"] <= 70),"TREND"] = "Bullish"
df.loc[(df["MOMENTUM_SCORE"] < 30),"TREND"] = "Bearish"

df.to_csv(output_file,index=False)

print("Momentum ranking created:",output_file)