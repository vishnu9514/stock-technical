import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

stocks_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

# -----------------------------------
# LOAD ALL STOCK DATA
# -----------------------------------

all_data = []

for file in os.listdir(stocks_folder):

    path = os.path.join(stocks_folder, file)

    try:
        df = pd.read_csv(path)

        if "DATE" not in df.columns:
            continue

        df["DATE"] = pd.to_datetime(df["DATE"])
        df["STOCK"] = file.replace(".csv", "")

        all_data.append(df)

    except:
        continue

df = pd.concat(all_data, ignore_index=True)

# -----------------------------------
# REQUIRED CHECK
# -----------------------------------

required_cols = ["DATE", "STOCK", "CLOSE", "MAIN_INDUSTRY"]

for col in required_cols:
    if col not in df.columns:
        raise Exception(f"❌ Missing column: {col}")

# -----------------------------------
# SORT
# -----------------------------------

df = df.sort_values(["DATE", "MAIN_INDUSTRY"])

# -----------------------------------
# DAILY LEADER (MOMENTUM BASED)
# -----------------------------------

df["RET_20"] = df.groupby("STOCK")["CLOSE"].pct_change(20)

leaders = (
    df.sort_values("RET_20", ascending=False)
    .groupby(["DATE", "MAIN_INDUSTRY"])
    .head(1)
)

# -----------------------------------
# BACKTEST
# -----------------------------------

capital = 100000
positions = {}
equity_curve = []

dates = sorted(leaders["DATE"].unique())

for date in dates:

    daily = leaders[leaders["DATE"] == date]

    new_positions = {}

    if len(daily) == 0:
        continue

    allocation = capital / len(daily)

    for _, row in daily.iterrows():

        ind = row["MAIN_INDUSTRY"]
        stock = row["STOCK"]
        price = row["CLOSE"]

        if ind in positions and positions[ind]["stock"] == stock:
            new_positions[ind] = positions[ind]
            continue

        new_positions[ind] = {
            "stock": stock,
            "entry_price": price,
            "value": allocation
        }

    total_value = 0

    for ind, pos in new_positions.items():

        stock = pos["stock"]

        current = df[
            (df["DATE"] == date) &
            (df["STOCK"] == stock)
        ]

        if current.empty:
            continue

        price = current["CLOSE"].values[0]

        ret = price / pos["entry_price"]
        value = pos["value"] * ret

        pos["value"] = value
        pos["entry_price"] = price

        total_value += value

    capital = total_value
    positions = new_positions

    equity_curve.append({
        "DATE": date,
        "CAPITAL": capital
    })

# -----------------------------------
# RESULTS
# -----------------------------------

equity_df = pd.DataFrame(equity_curve)

start = equity_df["CAPITAL"].iloc[0]
end = equity_df["CAPITAL"].iloc[-1]

years = (equity_df["DATE"].iloc[-1] - equity_df["DATE"].iloc[0]).days / 365

cagr = (end / start) ** (1 / years) - 1

equity_df["PEAK"] = equity_df["CAPITAL"].cummax()
equity_df["DD"] = (equity_df["CAPITAL"] - equity_df["PEAK"]) / equity_df["PEAK"]

max_dd = equity_df["DD"].min()

# -----------------------------------
# OUTPUT
# -----------------------------------

print("\n============================")
print("📊 REAL BACKTEST RESULT")
print("============================")
print(f"Start Capital: {start:,.0f}")
print(f"End Capital: {end:,.0f}")
print(f"CAGR %: {cagr*100:.2f}")
print(f"Max Drawdown %: {max_dd*100:.2f}")