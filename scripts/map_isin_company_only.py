import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -----------------------------------
# FILE PATH
# -----------------------------------

equity_file = os.path.join(BASE_DIR, "data", "EQUITY_L.csv")

folders = [
    "nse_stocks",
    "nse_weekly",
    "nse_monthly",
    "nse_quarterly"
]

# -----------------------------------
# CLEAN FUNCTION
# -----------------------------------

def clean_symbol(x):
    return (
        str(x)
        .upper()
        .strip()
        .replace(".NS", "")
        .replace("-EQ", "")
        .replace(".BO", "")
    )

# -----------------------------------
# LOAD EQUITY MASTER
# -----------------------------------

equity_df = pd.read_csv(equity_file)

print("📊 Columns in equity file:", equity_df.columns.tolist())

# -----------------------------------
# AUTO DETECT COLUMNS
# -----------------------------------

symbol_col = None
name_col = None
isin_col = None

for col in equity_df.columns:
    col_upper = col.upper()

    if "SYMBOL" in col_upper:
        symbol_col = col
    elif "NAME" in col_upper:
        name_col = col
    elif "ISIN" in col_upper:
        isin_col = col

if symbol_col is None or name_col is None or isin_col is None:
    print("❌ Column detection failed")
    exit()

# -----------------------------------
# CLEAN SYMBOLS
# -----------------------------------

equity_df["SYMBOL_CLEAN"] = equity_df[symbol_col].apply(clean_symbol)

# remove duplicates
equity_df = equity_df.drop_duplicates(subset=["SYMBOL_CLEAN"])

# create mapping
equity_dict = equity_df.set_index("SYMBOL_CLEAN")[[name_col, isin_col]].to_dict("index")

print(f"✅ Loaded {len(equity_dict)} symbols")

# -----------------------------------
# MAIN PROCESS
# -----------------------------------

missing = []

for folder in folders:

    folder_path = os.path.join(BASE_DIR, "data", folder)

    print(f"\n📂 Processing {folder}...")

    for file in os.listdir(folder_path):

        symbol_raw = file.replace(".csv", "")
        symbol = clean_symbol(symbol_raw)

        path = os.path.join(folder_path, file)

        try:
            df = pd.read_csv(path)
        except:
            continue

        # -----------------------------------
        # APPLY MAPPING
        # -----------------------------------

        if symbol in equity_dict:

            df["COMPANY_NAME"] = equity_dict[symbol][name_col]
            df["ISIN"] = equity_dict[symbol][isin_col]

        else:
            df["COMPANY_NAME"] = "UNKNOWN"
            df["ISIN"] = "UNKNOWN"
            missing.append(symbol)

        df.to_csv(path, index=False)

        print("✔", symbol)

# -----------------------------------
# REPORT
# -----------------------------------

print("\n======================")
print("📊 MISSING SYMBOLS")
print("======================")

print(list(set(missing))[:20])
print("Total missing:", len(set(missing)))

print("\n🔥 STEP 1 DONE: COMPANY + ISIN MAPPED")