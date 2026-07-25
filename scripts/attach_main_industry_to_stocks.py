import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mapping_file = os.path.join(BASE_DIR, "data", "main industries.xlsx")
stocks_folder = os.path.join(BASE_DIR, "data", "nse_stocks")

# -----------------------------------
# LOAD MAPPING
# -----------------------------------

mapping = pd.read_excel(mapping_file)
mapping.columns = mapping.columns.str.upper()

symbol_col = [c for c in mapping.columns if "SYMBOL" in c][0]
industry_col = [c for c in mapping.columns if "INDUSTRY" in c][0]

mapping["SYMBOL"] = mapping[symbol_col].astype(str).str.upper().str.strip()
mapping_dict = mapping.set_index("SYMBOL")[industry_col].to_dict()

print("✅ Mapping loaded:", len(mapping_dict))

# -----------------------------------
# APPLY TO ALL STOCK FILES
# -----------------------------------

for file in os.listdir(stocks_folder):

    symbol = file.replace(".csv", "").upper()
    path = os.path.join(stocks_folder, file)

    try:
        df = pd.read_csv(path)
    except:
        continue

    df["MAIN_INDUSTRY"] = mapping_dict.get(symbol, "UNKNOWN")

    df.to_csv(path, index=False)

print("\n🔥 MAIN INDUSTRY ADDED TO ALL STOCK FILES")