import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

daily_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")

output_file = os.path.join(BASE_DIR, "data", "stochrsi_M_W_D_scan.csv")

results = []

files = os.listdir(monthly_folder)

# -----------------------------------
# CONDITIONS
# -----------------------------------

def monthly_signal(df):
    if len(df) < 3:
        return False

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    return (
        curr["K"] < 30 and
        curr["D"] < 30 and
        curr["K"] > prev["K"]
    )

def weekly_signal(df):
    if len(df) < 3:
        return False

    curr = df.iloc[-1]

    return curr["K"] > curr["D"]

def daily_entry(df):
    if len(df) < 3:
        return False

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    return (
        curr["K"] > curr["D"] and
        prev["K"] < prev["D"]   # crossover
    )

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

    m_sig = monthly_signal(m)
    w_sig = weekly_signal(w)
    d_sig = daily_entry(d)

    if m_sig or w_sig or d_sig:

        results.append({

            "SYMBOL": symbol,

            # Monthly
            "M_K": round(m.iloc[-1]["K"], 2),
            "M_D": round(m.iloc[-1]["D"], 2),

            # Weekly
            "W_K": round(w.iloc[-1]["K"], 2),
            "W_D": round(w.iloc[-1]["D"], 2),

            # Daily
            "D_K": round(d.iloc[-1]["K"], 2),
            "D_D": round(d.iloc[-1]["D"], 2),

            # Signals
            "MONTHLY": m_sig,
            "WEEKLY": w_sig,
            "DAILY_ENTRY": d_sig,

            # Smart classification
            "SIGNAL_TYPE": (
                "BEST (M+W+D)" if (m_sig and w_sig and d_sig)
                else "STRONG (M+W)" if (m_sig and w_sig)
                else "EARLY (M)" if m_sig
                else "WEEKLY_ONLY" if w_sig
                else "DAILY_ONLY"
            )
        })

# -----------------------------------
# PRIORITY SORTING
# -----------------------------------

df = pd.DataFrame(results)

df["PRIORITY"] = 0

df.loc[df["SIGNAL_TYPE"] == "BEST (M+W+D)", "PRIORITY"] = 5
df.loc[df["SIGNAL_TYPE"] == "STRONG (M+W)", "PRIORITY"] = 4
df.loc[df["SIGNAL_TYPE"] == "EARLY (M)", "PRIORITY"] = 3
df.loc[df["SIGNAL_TYPE"] == "WEEKLY_ONLY", "PRIORITY"] = 2
df.loc[df["SIGNAL_TYPE"] == "DAILY_ONLY", "PRIORITY"] = 1

df = df.sort_values(["PRIORITY", "M_K"], ascending=[False, True])

df.to_csv(output_file, index=False)

print("✅ M + W + D StochRSI scan completed:", output_file)