import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

trades_file = os.path.join(BASE_DIR, "data", "accum_markup_leader_trades.csv")

# -----------------------------------
# PARAMETERS
# -----------------------------------

INITIAL_CAPITAL = 100000
RISK_PER_TRADE = 0.05   # 5% per trade

# -----------------------------------
# LOAD TRADES
# -----------------------------------

df = pd.read_csv(trades_file)

if "ENTRY_DATE" not in df.columns:
    print("❌ Trades file missing ENTRY_DATE")
    exit()

df["ENTRY_DATE"] = pd.to_datetime(df["ENTRY_DATE"])
df = df.sort_values("ENTRY_DATE")

print("✅ Trades loaded:", len(df))

# -----------------------------------
# BACKTEST ENGINE
# -----------------------------------

capital = INITIAL_CAPITAL
equity_curve = []
dates = []

for i, row in df.iterrows():

    trade_return = row["RETURN"]

    position_size = capital * RISK_PER_TRADE

    profit = position_size * trade_return

    capital += profit

    equity_curve.append(capital)
    dates.append(row["ENTRY_DATE"])

# -----------------------------------
# EQUITY DATAFRAME
# -----------------------------------

equity_df = pd.DataFrame({
    "DATE": dates,
    "EQUITY": equity_curve
})

# -----------------------------------
# CAGR
# -----------------------------------

days = (equity_df["DATE"].iloc[-1] - equity_df["DATE"].iloc[0]).days
years = days / 365

final_capital = equity_df["EQUITY"].iloc[-1]

cagr = ((final_capital / INITIAL_CAPITAL) ** (1 / years)) - 1

# -----------------------------------
# MAX DRAWDOWN
# -----------------------------------

equity_df["PEAK"] = equity_df["EQUITY"].cummax()
equity_df["DRAWDOWN"] = (equity_df["EQUITY"] - equity_df["PEAK"]) / equity_df["PEAK"]

max_dd = equity_df["DRAWDOWN"].min()

# -----------------------------------
# RESULTS
# -----------------------------------

print("\n============================")
print("📊 PROFESSIONAL BACKTEST")
print("============================")

print(f"Initial Capital: ₹{INITIAL_CAPITAL}")
print(f"Final Capital: ₹{round(final_capital, 2)}")

print(f"CAGR: {round(cagr * 100, 2)}%")
print(f"Max Drawdown: {round(max_dd * 100, 2)}%")

# -----------------------------------
# SAVE EQUITY CURVE
# -----------------------------------

equity_df.to_csv(
    os.path.join(BASE_DIR, "data", "equity_curve.csv"),
    index=False
)

print("\n🔥 Equity curve saved → equity_curve.csv")