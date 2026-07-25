import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

daily_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")
quarterly_folder = os.path.join(BASE_DIR, "data", "nse_quarterly")

# -----------------------------------
# FUNCTION: RESAMPLE WITH VOLUME
# -----------------------------------

def resample_data(df, timeframe):

    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.set_index("DATE")

    if "VOLUME" not in df.columns:
        df["VOLUME"] = 0

    agg = {
        "OPEN": "first",
        "HIGH": "max",
        "LOW": "min",
        "CLOSE": "last",
        "VOLUME": "sum"
    }

    if timeframe == "W":
        resampled = df.resample("W").agg(agg)

    elif timeframe == "M":
        resampled = df.resample("ME").agg(agg)   # ✅ FIX

    elif timeframe == "Q":
        resampled = df.resample("QE").agg(agg)   # ✅ FIX

    return resampled.dropna().reset_index()

# -----------------------------------
# MAIN PROCESS
# -----------------------------------

for file in os.listdir(daily_folder):

    path = os.path.join(daily_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    if "VOLUME" not in df.columns:
        print(f"❌ No volume in {file}")
        continue

    df = df.sort_values("DATE")

    # -----------------------------------
    # CREATE TIMEFRAMES
    # -----------------------------------

    weekly = resample_data(df.copy(), "W")
    monthly = resample_data(df.copy(), "M")
    quarterly = resample_data(df.copy(), "Q")

    # -----------------------------------
    # SAVE
    # -----------------------------------

    weekly.to_csv(os.path.join(weekly_folder, file), index=False)
    monthly.to_csv(os.path.join(monthly_folder, file), index=False)
    quarterly.to_csv(os.path.join(quarterly_folder, file), index=False)

    print(f"✔ Updated: {file}")

print("\n🔥 VOLUME ADDED TO ALL TIMEFRAMES")