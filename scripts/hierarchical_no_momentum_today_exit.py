import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

daily_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")

output_file = os.path.join(BASE_DIR, "data", "no_momentum_today_exit.csv")

results = []

# -----------------------------------
# CONDITION (NO MOMENTUM)
# -----------------------------------

def below_30(df, i):
    curr = df.iloc[i]
    return curr["K"] < 30 and curr["D"] < 30

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

    # latest (today)
    last_price = d.iloc[-1]["CLOSE"]
    last_date = d.iloc[-1]["DATE"]

    # -----------------------------------
    # FIND ENTRIES
    # -----------------------------------

    for i in range(20, len(d)):

        date = d.iloc[i]["DATE"]

        # get matching M/W
        m_row = m[m["DATE"] <= date]
        w_row = w[w["DATE"] <= date]

        if len(m_row) == 0 or len(w_row) == 0:
            continue

        m_idx = m_row.index[-1]
        w_idx = w_row.index[-1]

        m_ok = below_30(m, m_idx)
        w_ok = below_30(w, w_idx)
        d_ok = below_30(d, i)

        if not (m_ok and w_ok and d_ok):
            continue

        entry_price = d.iloc[i]["CLOSE"]
        entry_date = date

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

print("✅ Backtest (exit today) completed:", output_file)