import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

daily_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")
quarterly_folder = os.path.join(BASE_DIR, "data", "nse_quarterly")

def resample_safe(df, rule):

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

    return df.resample(rule).agg(agg).dropna().reset_index()

for file in os.listdir(daily_folder):

    path = os.path.join(daily_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    required = ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]
    if not all(col in df.columns for col in required):
        print(f"❌ Skipping {file}")
        continue

    df = df.sort_values("DATE")

    try:
        weekly = resample_safe(df.copy(), "W")
        monthly = resample_safe(df.copy(), "ME")   # ✅ FIX
        quarterly = resample_safe(df.copy(), "QE") # ✅ FIX
    except Exception as e:
        print(f"❌ Error in {file}: {e}")
        continue

    weekly.to_csv(os.path.join(weekly_folder, file), index=False)
    monthly.to_csv(os.path.join(monthly_folder, file), index=False)
    quarterly.to_csv(os.path.join(quarterly_folder, file), index=False)

    print(f"✔ {file}")

print("\n🔥 ALL TIMEFRAMES BUILT SUCCESSFULLY (UPDATED PANDAS FIX)")