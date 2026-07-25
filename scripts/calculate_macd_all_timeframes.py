import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

folders = [
    "nse_stocks",     # Daily
    "nse_weekly",     # Weekly
    "nse_monthly",    # Monthly
    "nse_quarterly"   # 3M
]

# -----------------------------------
# MACD FUNCTION
# -----------------------------------

def add_macd(df):

    df["EMA12"] = df["CLOSE"].ewm(span=12, adjust=False).mean()
    df["EMA26"] = df["CLOSE"].ewm(span=26, adjust=False).mean()

    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]

    return df

# -----------------------------------
# PROCESS ALL TIMEFRAMES
# -----------------------------------

for folder in folders:

    folder_path = os.path.join(BASE_DIR, "data", folder)

    print(f"\nProcessing {folder}...")

    files = os.listdir(folder_path)

    for file in files:

        path = os.path.join(folder_path, file)

        try:
            df = pd.read_csv(path)
        except:
            continue

        if "CLOSE" not in df.columns:
            continue

        df = df.sort_values("DATE")

        df = add_macd(df)

        df.to_csv(path, index=False)

        print("Updated:", file)

print("\n✅ MACD added to Daily, Weekly, Monthly, 3M")