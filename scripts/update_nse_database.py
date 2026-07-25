import os
from datetime import datetime

import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BHAVCOPY_FOLDER = os.path.join(BASE_DIR, "data", "nse_bhavcopy")
STOCK_FOLDER = os.path.join(BASE_DIR, "data", "nse_stocks")


def bhavcopy_date(filename):
    date_str = filename.split("_")[-1].replace(".csv", "")
    return datetime.strptime(date_str, "%d%m%Y")


def load_bhavcopy_records():
    files = [
        file
        for file in os.listdir(BHAVCOPY_FOLDER)
        if file.startswith("sec_bhavdata_full_") and file.endswith(".csv")
    ]
    files = sorted(files, key=bhavcopy_date)

    if not files:
        raise RuntimeError("No bhavcopy files found")

    stock_records = {}

    print(f"Reading {len(files):,} bhavcopy files...")

    for index, file in enumerate(files, start=1):
        path = os.path.join(BHAVCOPY_FOLDER, file)

        try:
            df = pd.read_csv(path)
        except Exception:
            continue

        df.columns = df.columns.str.strip()

        required = {
            "SYMBOL",
            "SERIES",
            "OPEN_PRICE",
            "HIGH_PRICE",
            "LOW_PRICE",
            "CLOSE_PRICE",
            "TTL_TRD_QNTY",
        }
        if not required.issubset(df.columns):
            continue

        df["SERIES"] = df["SERIES"].astype(str).str.strip()
        df = df[df["SERIES"] == "EQ"]

        date = pd.Timestamp(bhavcopy_date(file).date())

        for _, row in df.iterrows():
            symbol = str(row["SYMBOL"]).strip().upper()
            stock_records.setdefault(symbol, []).append(
                {
                    "DATE": date,
                    "OPEN": row["OPEN_PRICE"],
                    "HIGH": row["HIGH_PRICE"],
                    "LOW": row["LOW_PRICE"],
                    "CLOSE": row["CLOSE_PRICE"],
                    "VOLUME": row["TTL_TRD_QNTY"],
                }
            )

        if index % 250 == 0 or index == len(files):
            print(f"Loaded {index:,}/{len(files):,} bhavcopy files")

    return stock_records


def update_stock_file(file, records):
    path = os.path.join(STOCK_FOLDER, file)

    try:
        stock_df = pd.read_csv(path)
    except Exception:
        return False, 0

    if "DATE" not in stock_df.columns:
        return False, 0

    stock_df["DATE"] = pd.to_datetime(stock_df["DATE"], errors="coerce")
    existing_dates = set(stock_df["DATE"].dropna())

    new_rows = pd.DataFrame(records)
    new_rows["DATE"] = pd.to_datetime(new_rows["DATE"], errors="coerce")
    new_rows = new_rows[~new_rows["DATE"].isin(existing_dates)]

    if new_rows.empty:
        return True, 0

    stock_df = pd.concat([stock_df, new_rows], ignore_index=True)
    stock_df = stock_df.drop_duplicates(subset=["DATE"], keep="last")
    stock_df = stock_df.sort_values("DATE")
    stock_df.to_csv(path, index=False)

    return True, len(new_rows)


def main():
    if not os.path.exists(BHAVCOPY_FOLDER):
        raise FileNotFoundError(f"Folder not found: {BHAVCOPY_FOLDER}")
    if not os.path.exists(STOCK_FOLDER):
        raise FileNotFoundError(f"Folder not found: {STOCK_FOLDER}")

    stock_records = load_bhavcopy_records()

    updated_files = 0
    added_rows = 0

    stock_files = [file for file in os.listdir(STOCK_FOLDER) if file.endswith(".csv")]

    print(f"Updating {len(stock_files):,} stock files...")

    for index, file in enumerate(stock_files, start=1):
        symbol = os.path.splitext(file)[0].upper()
        records = stock_records.get(symbol)

        if not records:
            continue

        processed, rows = update_stock_file(file, records)
        if processed:
            updated_files += 1
            added_rows += rows

        if index % 250 == 0 or index == len(stock_files):
            print(f"Processed {index:,}/{len(stock_files):,} stock files")

    print("\nNSE database update completed")
    print(f"Files checked: {updated_files:,}")
    print(f"New daily rows added: {added_rows:,}")


if __name__ == "__main__":
    main()
