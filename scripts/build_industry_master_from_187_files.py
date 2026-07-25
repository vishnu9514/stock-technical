import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

industry_folder = os.path.join(BASE_DIR, "data", "industry_files")
output_file = os.path.join(BASE_DIR, "data", "industry_master.csv")

all_data = []

# -----------------------------------
# LOOP ALL INDUSTRY FILES
# -----------------------------------

for file in os.listdir(industry_folder):

    if not file.endswith(".csv"):
        continue

    industry_name = file.replace(".csv", "").replace("_", " ")

    path = os.path.join(industry_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    # -----------------------------------
    # FIND SYMBOL COLUMN
    # -----------------------------------

    possible_cols = ["SYMBOL", "Symbol", "symbol", "STOCK", "Stock"]

    symbol_col = None
    for col in possible_cols:
        if col in df.columns:
            symbol_col = col
            break

    if symbol_col is None:
        print(f"❌ No symbol column in {file}")
        continue

    # -----------------------------------
    # CREATE MAPPING
    # -----------------------------------

    temp = pd.DataFrame()
    temp["SYMBOL"] = df[symbol_col].astype(str).str.upper().str.strip()
    temp["INDUSTRY"] = industry_name
    temp["SECTOR"] = "UNKNOWN"  # can update later

    all_data.append(temp)

# -----------------------------------
# MERGE ALL
# -----------------------------------

master = pd.concat(all_data, ignore_index=True)

# remove duplicates
master = master.drop_duplicates(subset=["SYMBOL"])

# save
master.to_csv(output_file, index=False)

print("\n✅ industry_master.csv created successfully")