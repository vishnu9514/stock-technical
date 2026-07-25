import pandas as pd
import os

# project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")

output_file = os.path.join(BASE_DIR, "data", "stochrsi_1M_W_scan.csv")

results = []

files = os.listdir(monthly_folder)

# -----------------------------
# CONDITIONS
# -----------------------------
def monthly_signal(df):
    if len(df) < 3:
        return False

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    # Early stage momentum
    return (
        curr["K"] < 25 and
        curr["D"] < 25 and
        curr["K"] > prev["K"]
    )

def weekly_confirmation(df):
    if len(df) < 3:
        return False

    curr = df.iloc[-1]

    return curr["K"] > curr["D"]


# -----------------------------
# MAIN LOOP
# -----------------------------
for file in files:

    symbol = file.replace(".csv", "")

    try:
        m = pd.read_csv(os.path.join(monthly_folder, file))
        w = pd.read_csv(os.path.join(weekly_folder, file))
    except:
        continue

    m_signal = monthly_signal(m)
    w_signal = weekly_confirmation(w)

    if m_signal or w_signal:

        results.append({

            "SYMBOL": symbol,

            # Monthly
            "M_K": round(m.iloc[-1]["K"], 2),
            "M_D": round(m.iloc[-1]["D"], 2),

            # Weekly
            "W_K": round(w.iloc[-1]["K"], 2),
            "W_D": round(w.iloc[-1]["D"], 2),

            # Signals
            "MONTHLY_SIGNAL": m_signal,
            "WEEKLY_CONFIRM": w_signal,

            # Combined strength
            "SIGNAL_TYPE": (
                "STRONG (1M+W)" if (m_signal and w_signal)
                else "EARLY (1M)" if m_signal
                else "W_ONLY"
            )
        })

# -----------------------------
# SAVE OUTPUT
# -----------------------------
df = pd.DataFrame(results)

# rank strong setups first
df["PRIORITY"] = 0
df.loc[df["SIGNAL_TYPE"] == "STRONG (1M+W)", "PRIORITY"] = 3
df.loc[df["SIGNAL_TYPE"] == "EARLY (1M)", "PRIORITY"] = 2
df.loc[df["SIGNAL_TYPE"] == "W_ONLY", "PRIORITY"] = 1

df = df.sort_values(["PRIORITY", "M_K"], ascending=[False, True])

df.to_csv(output_file, index=False)

print("✅ 1M + Weekly StochRSI scan completed:", output_file)