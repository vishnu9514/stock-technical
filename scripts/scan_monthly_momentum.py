import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")

results = []

files = os.listdir(monthly_folder)


def monthly_momentum(df):

    if len(df) < 3:
        return False

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    if curr["K"] < 20 and curr["D"] < 20 and curr["K"] > prev["K"]:
        return True

    return False


for file in files:

    symbol = file.replace(".csv", "")

    try:
        df = pd.read_csv(os.path.join(monthly_folder, file))
    except:
        continue

    signal = monthly_momentum(df)

    if signal:

        results.append({
            "SYMBOL": symbol,
            "M_K": round(df.iloc[-1]["K"], 2),
            "M_D": round(df.iloc[-1]["D"], 2)
        })


result_df = pd.DataFrame(results)

output = os.path.join(BASE_DIR, "data", "monthly_stochrsi_momentum.csv")

result_df.to_csv(output, index=False)

print("Monthly momentum scan completed:", output)