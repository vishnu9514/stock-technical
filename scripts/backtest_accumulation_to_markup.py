import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

leaders_file = os.path.join(BASE_DIR, "data", "historical_leaders.csv")
industry_file = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")  
data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

HOLD_DAYS = 20

# -----------------------------------
# LOAD DATA
# -----------------------------------

leaders = pd.read_csv(leaders_file)
leaders["DATE"] = pd.to_datetime(leaders["DATE"])

industry = pd.read_csv(industry_file)
industry["DATE"] = pd.to_datetime(industry["DATE"])

# -----------------------------------
# SORT INDUSTRY
# -----------------------------------

industry = industry.sort_values(["MAIN_INDUSTRY", "DATE"])

# -----------------------------------
# DETECT TRANSITION
# -----------------------------------

industry["PREV_PHASE"] = industry.groupby("MAIN_INDUSTRY")["PHASE"].shift(1)

# ✅ ONLY ACCUMULATION → MARKUP
industry["SIGNAL"] = (
    (industry["PREV_PHASE"] == "ACCUMULATION") &
    (industry["PHASE"] == "MARKUP")
)

signals = industry[industry["SIGNAL"] == True]

print("✅ Total signals:", len(signals))

# -----------------------------------
# LOAD STOCK DATA
# -----------------------------------

stock_data = {}

for file in os.listdir(data_folder):

    symbol = file.replace(".csv", "").upper()
    path = os.path.join(data_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "DATE" not in df.columns:
        continue

    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE").reset_index(drop=True)

    stock_data[symbol] = df

# -----------------------------------
# BACKTEST
# -----------------------------------

results = []
trade_details = []

for _, row in signals.iterrows():

    industry_name = row["MAIN_INDUSTRY"]
    signal_date = row["DATE"]

    # find leader on same date
    leader_row = leaders[
        (leaders["DATE"] == signal_date) &
        (leaders["MAIN_INDUSTRY"] == industry_name)
    ]

    if leader_row.empty:
        continue

    stock = leader_row.iloc[0]["STOCK"]

    if stock not in stock_data:
        continue

    df = stock_data[stock]

    # next trading day entry
    future = df[df["DATE"] > signal_date]

    if future.empty:
        continue

    entry_row = future.iloc[0]
    entry_idx = entry_row.name
    entry_price = entry_row["OPEN"]

    exit_idx = entry_idx + HOLD_DAYS

    if exit_idx >= len(df):
        continue

    exit_row = df.iloc[exit_idx]
    exit_price = exit_row["CLOSE"]

    ret = (exit_price - entry_price) / entry_price

    results.append(ret)

    trade_details.append({
        "INDUSTRY": industry_name,
        "STOCK": stock,
        "ENTRY_DATE": entry_row["DATE"],
        "EXIT_DATE": exit_row["DATE"],
        "RETURN": ret
    })

# -----------------------------------
# RESULTS
# -----------------------------------

if len(results) == 0:
    print("\n❌ NO TRADES → check industry dashboard file")
    exit()

results = pd.Series(results)

print("\n============================")
print("📊 ACCUMULATION → MARKUP BACKTEST")
print("============================")

print("Total Trades:", len(results))
win_rate = float((results > 0).mean() * 100)
avg_return = float(results.mean() * 100)
cumulative = 1.0
for r in results:
    cumulative *= (1.0 + r)
total_return = (cumulative - 1.0) * 100

print("Win Rate %:", round(win_rate, 2))
print("Avg Return %:", round(avg_return, 2))
print("Total Return %:", round(total_return, 2))

# save trades
pd.DataFrame(trade_details).to_csv(
    os.path.join(BASE_DIR, "data", "accumulation_markup_trades.csv"),
    index=False
)

print("\n🔥 STRATEGY BACKTEST COMPLETE")