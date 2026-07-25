import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

folders = {
    "D": "nse_stocks",
    "W": "nse_weekly",
    "M": "nse_monthly",
    "3M": "nse_quarterly"
}

output_file = os.path.join(BASE_DIR, "data", "macd_dashboard.csv")

results = []

files = os.listdir(os.path.join(BASE_DIR, "data", "nse_stocks"))

# -----------------------------------
# MACD STATUS FUNCTION
# -----------------------------------

def macd_status(df):
    if len(df) < 2:
        return None

    row = df.iloc[-1]

    if row["MACD"] > row["MACD_SIGNAL"]:
        return "Bullish"
    else:
        return "Bearish"

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

    d_status = macd_status(d)
    w_status = macd_status(w)
    m_status = macd_status(m)
    q_status = macd_status(q)

    # alignment score
    score = (
        (q_status == "Bullish") * 40 +
        (m_status == "Bullish") * 30 +
        (w_status == "Bullish") * 20 +
        (d_status == "Bullish") * 10
    )

    results.append({
        "SYMBOL": symbol,
        "3M_MACD": q_status,
        "M_MACD": m_status,
        "W_MACD": w_status,
        "D_MACD": d_status,
        "ALIGNMENT_SCORE": score
    })

# -----------------------------------
# SAVE
# -----------------------------------

df = pd.DataFrame(results)

df = df.sort_values("ALIGNMENT_SCORE", ascending=False)

df.to_csv(output_file, index=False)

print("✅ MACD dashboard created:", output_file)