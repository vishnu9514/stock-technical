import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

folders = {
    "D": "nse_stocks",
    "W": "nse_weekly",
    "M": "nse_monthly",
    "3M": "nse_quarterly"
}

output_file = os.path.join(BASE_DIR, "data", "elliott_dashboard.csv")

results = []

files = os.listdir(os.path.join(BASE_DIR, "data", "nse_stocks"))

# -----------------------------------
# STATUS FUNCTION
# -----------------------------------

def elliott_status(df):

    if "ELLIOTT_TRENDLINE" not in df.columns:
        return None

    df = df.dropna(subset=["ELLIOTT_TRENDLINE"])

    if len(df) == 0:
        return None

    row = df.iloc[-1]

    if row["CLOSE"] > row["ELLIOTT_TRENDLINE"]:
        return "Above"
    else:
        return "Below"

# -----------------------------------
# MAIN LOOP
# -----------------------------------

for file in files:

    symbol = file.replace(".csv", "")

    try:
        d = pd.read_csv(os.path.join(BASE_DIR, "data", folders["D"], file))
        w = pd.read_csv(os.path.join(BASE_DIR, "data", folders["W"], file))
        m = pd.read_csv(os.path.join(BASE_DIR, "data", folders["M"], file))
        q = pd.read_csv(os.path.join(BASE_DIR, "data", folders["3M"], file))
    except:
        continue

    d_stat = elliott_status(d)
    w_stat = elliott_status(w)
    m_stat = elliott_status(m)
    q_stat = elliott_status(q)

    # scoring
    score = (
        (q_stat == "Above") * 40 +
        (m_stat == "Above") * 30 +
        (w_stat == "Above") * 20 +
        (d_stat == "Above") * 10
    )

    results.append({
        "SYMBOL": symbol,
        "3M_STRUCTURE": q_stat,
        "M_STRUCTURE": m_stat,
        "W_STRUCTURE": w_stat,
        "D_STRUCTURE": d_stat,
        "STRUCTURE_SCORE": score
    })

# -----------------------------------
# SAVE
# -----------------------------------

df = pd.DataFrame(results)

df = df.sort_values("STRUCTURE_SCORE", ascending=False)

df.to_csv(output_file, index=False)

print("✅ Elliott structure dashboard created:", output_file)