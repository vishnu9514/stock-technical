import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -----------------------------------
# FILE PATH
# -----------------------------------

mapping_file = os.path.join(BASE_DIR, "data", "industry_with_sector_with_isin.csv")

folders = [
    "nse_stocks",
    "nse_weekly",
    "nse_monthly",
    "nse_quarterly"
]

# -----------------------------------
# CLEAN FUNCTION
# -----------------------------------

def clean_text(x):
    return str(x).upper().strip()

# -----------------------------------
# LOAD MAPPING FILE
# -----------------------------------

mapping_df = pd.read_csv(mapping_file)

print("📊 Mapping columns:", mapping_df.columns.tolist())

# auto-detect columns
isin_col = [c for c in mapping_df.columns if "ISIN" in c.upper()][0]
industry_col = [c for c in mapping_df.columns if "INDUSTRY" in c.upper()][0]
sector_col = [c for c in mapping_df.columns if "SECTOR" in c.upper()][0]

# -----------------------------------
# CLEAN + FIX DUPLICATES
# -----------------------------------

mapping_df["ISIN_CLEAN"] = mapping_df[isin_col].apply(clean_text)

# remove duplicate ISINs (IMPORTANT FIX)
mapping_df = mapping_df.drop_duplicates(subset=["ISIN_CLEAN"])

print(f"✅ Unique ISIN count: {len(mapping_df)}")

# create mapping dictionary
mapping_dict = mapping_df.set_index("ISIN_CLEAN")[[industry_col, sector_col]].to_dict("index")

# -----------------------------------
# MAIN PROCESS
# -----------------------------------

missing = []

for folder in folders:

    folder_path = os.path.join(BASE_DIR, "data", folder)

    print(f"\n📂 Processing {folder}...")

    for file in os.listdir(folder_path):

        path = os.path.join(folder_path, file)

        try:
            df = pd.read_csv(path)
        except:
            continue

        # -----------------------------------
        # REMOVE OLD COLUMNS
        # -----------------------------------

        df = df.drop(columns=["INDUSTRY", "SECTOR"], errors="ignore")

        # -----------------------------------
        # CHECK ISIN COLUMN
        # -----------------------------------

        if "ISIN" not in df.columns:
            df["INDUSTRY"] = "UNKNOWN"
            df["SECTOR"] = "UNKNOWN"
            missing.append(file)
            df.to_csv(path, index=False)
            continue

        isin = clean_text(df["ISIN"].iloc[0])

        # -----------------------------------
        # MAP USING ISIN
        # -----------------------------------

        if isin in mapping_dict:
            df["INDUSTRY"] = mapping_dict[isin][industry_col]
            df["SECTOR"] = mapping_dict[isin][sector_col]
        else:
            df["INDUSTRY"] = "UNKNOWN"
            df["SECTOR"] = "UNKNOWN"
            missing.append(isin)

        # -----------------------------------
        # SAVE
        # -----------------------------------

        df.to_csv(path, index=False)

        print("✔", file)

# -----------------------------------
# FINAL REPORT
# -----------------------------------

print("\n==============================")
print("📊 FINAL REPORT")
print("==============================")

print("Missing examples:", list(set(missing))[:20])
print("Total missing:", len(set(missing)))

print("\n🔥 ALL TIMEFRAMES UPDATED SUCCESSFULLY (ISIN BASED)")