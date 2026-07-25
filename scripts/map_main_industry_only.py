import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mapping_file = os.path.join(BASE_DIR, "data", "main industries.xlsx")
data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

# -----------------------------------
# LOAD EXCEL (IMPORTANT FIX)
# -----------------------------------

mapping_df = pd.read_excel(mapping_file)

# CLEAN COLUMN NAMES
mapping_df.columns = mapping_df.columns.str.strip().str.upper()

# EXPECTED COLUMNS (adjust if needed)
# SYMBOL / COMPANY / MAIN_INDUSTRY

# Try to auto-detect
symbol_col = [c for c in mapping_df.columns if "SYMBOL" in c][0]
industry_col = [c for c in mapping_df.columns if "INDUSTRY" in c][0]

mapping_df["SYMBOL"] = mapping_df[symbol_col].astype(str).str.upper().str.strip()

mapping_dict = mapping_df.set_index("SYMBOL")[industry_col].to_dict()

print("✅ Mapping loaded:", len(mapping_dict))

# -----------------------------------
# APPLY TO ALL STOCK FILES
# -----------------------------------

for file in os.listdir(data_folder):

    symbol = file.replace(".csv", "").upper()

    path = os.path.join(data_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    # REMOVE OLD
    if "MAIN_INDUSTRY" in df.columns:
        df.drop(columns=["MAIN_INDUSTRY"], inplace=True)

    # MAP
    df["MAIN_INDUSTRY"] = mapping_dict.get(symbol, "UNKNOWN")

    df.to_csv(path, index=False)

print("\n🔥 MAIN INDUSTRY MAPPING COMPLETE")