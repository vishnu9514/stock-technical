import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

leaders_file = os.path.join(BASE_DIR, "data", "historical_leaders.csv")
industry_file = os.path.join(BASE_DIR, "data", "main_industry_dashboard_full.csv")
data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

HOLD_DAYS = 20

# -----------------------------------
# LOAD FILES
# -----------------------------------

leaders = pd.read_csv(leaders_file)
leaders["DATE"] = pd.to_datetime(leaders["DATE"])

industry = pd.read_csv(industry_file)
industry["DATE"] = pd.to_datetime(industry["DATE"])

# -----------------------------------
# SORT INDUSTRY DATA
# -----------------------------------

industry = industry.sort_values(["MAIN_INDUSTRY", "DATE"])

# -----------------------------------
# FIND ACCUMULATION → MARKUP SIGNAL
# -----------------------------------

industry["PREV_PHASE"] = industry.groupby("MAIN_INDUSTRY")["PHASE"].shift(1)

signals = industry[
    (industry["PREV_PHASE"] == "ACCUMULATION") &
    (industry["PHASE"] == "MARKUP")
]

print("✅ Signals found:", len(signals))

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
trades = []

for _, row in signals.iterrows():

    ind = row["MAIN_INDUSTRY"]
    signal_date = row["DATE"]

    # get leader for that day + industry
    leader = leaders[
        (leaders["DATE"] == signal_date) &
        (leaders["MAIN_INDUSTRY"] == ind)
    ]

    if leader.empty:
        continue

    stock = leader.iloc[0]["STOCK"]

    if stock not in stock_data:
        continue

    df = stock_data[stock]

    # entry = next trading day
    future = df[df["DATE"] > signal_date]

    if future.empty:
        continue

    entry_row = future.iloc[0]
    entry_idx = entry_row.name
    entry_price = entry_row["OPEN"]

    # exit
    exit_idx = entry_idx + HOLD_DAYS

    if exit_idx >= len(df):
        continue

    exit_row = df.iloc[exit_idx]
    exit_price = exit_row["CLOSE"]

    ret = (exit_price - entry_price) / entry_price

    results.append(ret)

    trades.append({
        "INDUSTRY": ind,
        "STOCK": stock,
        "ENTRY_DATE": entry_row["DATE"],
        "EXIT_DATE": exit_row["DATE"],
        "RETURN": ret
    })

# -----------------------------------
# RESULTS
# -----------------------------------

if len(results) == 0:
    print("\n❌ No trades executed — check inputs")
    exit()

results = pd.Series(results)

print("\n============================")
print("📊 ACCUMULATION → MARKUP LEADER STRATEGY")
print("============================")

print("Total Trades:", len(results))
print("Win Rate %:", round((results > 0).mean() * 100, 2))
print("Avg Return %:", round(results.mean() * 100, 2))
print("Total Return %:", round(((results + 1).prod() - 1) * 100, 2))

# save trades
pd.DataFrame(trades).to_csv(
    os.path.join(BASE_DIR, "data", "accum_markup_leader_trades.csv"),
    index=False
)

print("\n🔥 STRATEGY COMPLETE")