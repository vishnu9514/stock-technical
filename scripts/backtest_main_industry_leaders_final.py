import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

leaders_file = os.path.join(BASE_DIR, "data", "historical_leaders.csv")
data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

HOLD_DAYS = 20

# -----------------------------------
# LOAD LEADERS
# -----------------------------------

leaders = pd.read_csv(leaders_file)
leaders["DATE"] = pd.to_datetime(leaders["DATE"])

print("✅ Leaders loaded:", len(leaders))

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

print("✅ Stocks loaded:", len(stock_data))

# -----------------------------------
# BACKTEST
# -----------------------------------

results = []
trade_details = []

for _, row in leaders.iterrows():

    stock = row["STOCK"]
    entry_date = row["DATE"]

    if stock not in stock_data:
        continue

    df = stock_data[stock]

    # find next trading day
    future = df[df["DATE"] > entry_date]

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
        "STOCK": stock,
        "ENTRY_DATE": entry_row["DATE"],
        "EXIT_DATE": exit_row["DATE"],
        "RETURN": ret
    })

# -----------------------------------
# RESULTS
# -----------------------------------

if len(results) == 0:
    print("\n❌ STILL NO TRADES → CHECK FILE")
    exit()

results = pd.Series(results)

print("\n============================")
print("📊 BACKTEST RESULT")
print("============================")

print("Total Trades:", len(results))
print("Win Rate %:", round((results > 0).mean() * 100, 2))
print("Avg Return %:", round(results.mean() * 100, 2))
print("Total Return %:", round(((results + 1).prod() - 1) * 100, 2))

# save trades
pd.DataFrame(trade_details).to_csv(
    os.path.join(BASE_DIR, "data", "leader_backtest_trades.csv"),
    index=False
)

print("\n🔥 BACKTEST COMPLETE")