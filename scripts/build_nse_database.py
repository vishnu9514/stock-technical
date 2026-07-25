import pandas as pd
import os

# detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

source_folder = os.path.join(BASE_DIR, "data", "nse_bhavcopy")
output_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

os.makedirs(output_folder, exist_ok=True)

files = sorted(os.listdir(source_folder))

stock_data = {}

print("Reading NSE bhavcopy files...")

for file in files:

    if not file.endswith(".csv"):
        continue

    path = os.path.join(source_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        print("Skipping corrupted file:", file)
        continue

    df.columns = df.columns.str.strip()

    if "SERIES" not in df.columns:
        print("Invalid file:", file)
        continue

    df["SERIES"] = df["SERIES"].astype(str).str.strip()

    # keep equity stocks only
    df = df[df["SERIES"] == "EQ"]

    # extract date from filename
    try:
        date_str = file.split("_")[-1].replace(".csv", "")
    except:
        print("Bad filename:", file)
        continue

    print(file, "EQ rows:", len(df))

    for _, row in df.iterrows():

        symbol = str(row["SYMBOL"]).strip()

        record = {
            "DATE": date_str,
            "OPEN": row["OPEN_PRICE"],
            "HIGH": row["HIGH_PRICE"],
            "LOW": row["LOW_PRICE"],
            "CLOSE": row["CLOSE_PRICE"],
            "VOLUME": row["TTL_TRD_QNTY"]
        }

        if symbol not in stock_data:
            stock_data[symbol] = []

        stock_data[symbol].append(record)


print("Building stock database...")

for symbol in stock_data:

    df = pd.DataFrame(stock_data[symbol])

    if df["VOLUME"].sum() == 0:
        continue

    try:
        df["DATE"] = pd.to_datetime(df["DATE"], format="%d%m%Y")
    except:
        print("Date error:", symbol)
        continue

    df = df.sort_values("DATE")

    output_path = os.path.join(output_folder, f"{symbol}.csv")

    df.to_csv(output_path, index=False)

print("NSE stock database build completed")