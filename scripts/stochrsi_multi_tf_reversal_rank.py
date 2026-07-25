import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

daily_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")

output_file = os.path.join(BASE_DIR, "data", "stochrsi_reversal_multi_tf_rank.csv")

results = []

files = os.listdir(monthly_folder)

# -----------------------------------
# REVERSAL LOGIC
# -----------------------------------

def reversal_signal(df):
    if len(df) < 3:
        return False, 0

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    k, d = curr["K"], curr["D"]

    if pd.isna(k) or pd.isna(d):
        return False, 0

    # condition: oversold + turning up
    oversold = (k < 20 and d < 20)
    turning_up = (k > prev["K"])
    crossover = (k > d and prev["K"] < prev["D"])

    signal = oversold and (turning_up or crossover)

    # strength score
    score = 0

    if oversold:
        score += 20

    if turning_up:
        score += 15

    if crossover:
        score += 25

    # deeper oversold = stronger
    score += max(0, (20 - k)) * 1.5

    return signal, round(score, 2)


# -----------------------------------
# MAIN LOOP
# -----------------------------------

for file in files:

    symbol = file.replace(".csv", "")

    try:
        m = pd.read_csv(os.path.join(monthly_folder, file))
        w = pd.read_csv(os.path.join(weekly_folder, file))
        d = pd.read_csv(os.path.join(daily_folder, file))
    except:
        continue

    m_sig, m_score = reversal_signal(m)
    w_sig, w_score = reversal_signal(w)
    d_sig, d_score = reversal_signal(d)

    # keep only if at least 1 timeframe signals
    if not (m_sig or w_sig or d_sig):
        continue

    # -----------------------------------
    # COMBINED SCORE
    # -----------------------------------

    total_score = (
        m_score * 0.5 +   # highest weight
        w_score * 0.3 +
        d_score * 0.2
    )

    results.append({

        "SYMBOL": symbol,

        # Monthly
        "M_K": round(m.iloc[-1]["K"], 2),
        "M_D": round(m.iloc[-1]["D"], 2),
        "M_SIGNAL": m_sig,

        # Weekly
        "W_K": round(w.iloc[-1]["K"], 2),
        "W_D": round(w.iloc[-1]["D"], 2),
        "W_SIGNAL": w_sig,

        # Daily
        "D_K": round(d.iloc[-1]["K"], 2),
        "D_D": round(d.iloc[-1]["D"], 2),
        "D_SIGNAL": d_sig,

        "TOTAL_SCORE": round(total_score, 2),

        # classification
        "SETUP_TYPE": (
            "ULTIMATE (M+W+D)" if (m_sig and w_sig and d_sig)
            else "HIGH (M+W)" if (m_sig and w_sig)
            else "MEDIUM (W+D)" if (w_sig and d_sig)
            else "EARLY (M)" if m_sig
            else "WEAK"
        )
    })


# -----------------------------------
# FINAL RANKING
# -----------------------------------

df = pd.DataFrame(results)

df = df.sort_values("TOTAL_SCORE", ascending=False)

df["RANK"] = range(1, len(df) + 1)

df.to_csv(output_file, index=False)

print("✅ Multi-timeframe reversal ranking created:", output_file)