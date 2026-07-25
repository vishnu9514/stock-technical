import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

industry_file = os.path.join(BASE_DIR, "data", "industry_with_sector.csv")
equity_file = os.path.join(BASE_DIR, "data", "EQUITY_L.csv")

output_file = os.path.join(BASE_DIR, "data", "industry_with_sector_with_isin.csv")

# -----------------------------------
# CLEAN FUNCTION
# -----------------------------------

def clean_text(x):
    return str(x).upper().strip()

# -----------------------------------
# LOAD FILES
# -----------------------------------

industry_df = pd.read_csv(industry_file)
equity_df = pd.read_csv(equity_file)

print("📊 Industry columns:", industry_df.columns.tolist())
print("📊 Equity columns:", equity_df.columns.tolist())

# -----------------------------------
# DETECT COLUMNS
# -----------------------------------

industry_name_col = "symbol"  # your file confirmed

name_col = [c for c in equity_df.columns if "NAME" in c.upper()][0]
isin_col = [c for c in equity_df.columns if "ISIN" in c.upper()][0]

# -----------------------------------
# CLEAN TEXT
# -----------------------------------

industry_df["NAME_CLEAN"] = industry_df[industry_name_col].apply(clean_text)
equity_df["NAME_CLEAN"] = equity_df[name_col].apply(clean_text)

# -----------------------------------
# CREATE MAPPING
# -----------------------------------

equity_dict = equity_df.set_index("NAME_CLEAN")[isin_col].to_dict()

# -----------------------------------
# ADD ISIN
# -----------------------------------

missing = []

isin_list = []

for name in industry_df["NAME_CLEAN"]:

    if name in equity_dict:
        isin_list.append(equity_dict[name])
    else:
        isin_list.append("UNKNOWN")
        missing.append(name)

industry_df["ISIN"] = isin_list

# -----------------------------------
# CLEAN OUTPUT
# -----------------------------------

industry_df.drop(columns=["NAME_CLEAN"], inplace=True)

industry_df.to_csv(output_file, index=False)

# -----------------------------------
# REPORT
# -----------------------------------

print("\n======================")
print("📊 RESULT")
print("======================")

print("Missing examples:", missing[:20])
print("Total missing:", len(missing))

print("\n🔥 FILE CREATED:")
print(output_file)