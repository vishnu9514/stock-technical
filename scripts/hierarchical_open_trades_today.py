import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

daily_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")

output_file = os.path.join(BASE_DIR, "data", "open_trades_today.csv")

results = []

# -----------------------------------
# SIGNAL FUNCTION
# -----------------------------------

def momentum_signal(df, i):
    if i < 2:
        return False

    prev = df.iloc[i-1]
    curr = df.iloc[i]

    return (
        curr["K"] < 20 and
        curr["D"] < 20 and
        curr["K"] > prev["K"]
    )

# -----------------------------------
# MAIN LOOP
# -----------------------------------

files = os.listdir(monthly_folder)

for file in files:

    symbol = file.replace(".csv", "")

    try:
        m = pd.read_csv(os.path.join(monthly_folder, file))
        w = pd.read_csv(os.path.join(weekly_folder, file))
        d = pd.read_csv(os.path.join(daily_folder, file))
    except:
        continue

    m["DATE"] = pd.to_datetime(m["DATE"])
    w["DATE"] = pd.to_datetime(w["DATE"])
    d["DATE"] = pd.to_datetime(d["DATE"])

    m = m.sort_values("DATE")
    w = w.sort_values("DATE")
    d = d.sort_values("DATE")

    last_price = d.iloc[-1]["CLOSE"]
    last_date = d.iloc[-1]["DATE"]

    # -----------------------------------
    # FIND ENTRIES
    # -----------------------------------

    for i in range(20, len(d)):

        date = d.iloc[i]["DATE"]

        m_row = m[m["DATE"] <= date]
        w_row = w[w["DATE"] <= date]

        if len(m_row) < 2 or len(w_row) < 2:
            continue

        m_idx = m_row.index[-1]
        w_idx = w_row.index[-1]

        m_ok = momentum_signal(m, m_idx)
        w_ok = momentum_signal(w, w_idx)
        d_ok = momentum_signal(d, i)

        if not (m_ok and w_ok and d_ok):
            continue

        entry_price = d.iloc[i]["CLOSE"]
        entry_date = date

        # -----------------------------------
        # EXIT = TODAY
        # -----------------------------------

        pnl = (last_price - entry_price) / entry_price * 100

        results.append({
            "SYMBOL": symbol,
            "ENTRY_DATE": entry_date,
            "ENTRY_PRICE": entry_price,
            "CURRENT_PRICE": last_price,
            "CURRENT_DATE": last_date,
            "HOLD_DAYS": (last_date - entry_date).days,
            "RETURN_%": round(pnl, 2)
        })

# -----------------------------------
# SAVE OUTPUT
# -----------------------------------

df = pd.DataFrame(results)

df = df.sort_values("RETURN_%", ascending=False)

df.to_csv(output_file, index=False)

print("✅ Open trades (till today) created:", output_file)