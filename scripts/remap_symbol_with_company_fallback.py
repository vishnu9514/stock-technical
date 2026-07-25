import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mapping_file = os.path.join(BASE_DIR, "data", "industry_with_sector.csv")

folders = [
    "nse_stocks",
    "nse_weekly",
    "nse_monthly",
    "nse_quarterly"
]

# -----------------------------------
# CLEAN FUNCTIONS
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

def clean_text(x):
    return str(x).upper().strip()

# -----------------------------------
# LOAD MAPPING
# -----------------------------------

mapping_df = pd.read_csv(mapping_file)

print("📊 Mapping columns:", mapping_df.columns.tolist())

# clean symbol
mapping_df["SYMBOL_CLEAN"] = mapping_df["symbol"].apply(clean_symbol)

# also prepare name (optional future use)
mapping_df["NAME_CLEAN"] = mapping_df["symbol"].apply(clean_text)

mapping_dict = mapping_df.set_index("SYMBOL_CLEAN")[["industry", "sector"]].to_dict("index")

print(f"✅ Loaded {len(mapping_dict)} mappings")

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
        # REMOVE OLD COLUMNS
        # -----------------------------------

        df = df.drop(columns=["INDUSTRY", "SECTOR"], errors="ignore")

        # -----------------------------------
        # PRIMARY MATCH (SYMBOL)
        # -----------------------------------

        if symbol in mapping_dict:

            df["INDUSTRY"] = mapping_dict[symbol]["industry"]
            df["SECTOR"] = mapping_dict[symbol]["sector"]

        else:
            # -----------------------------------
            # FALLBACK MATCH (COMPANY NAME)
            # -----------------------------------

            if "COMPANY_NAME" in df.columns:

                company = clean_text(df["COMPANY_NAME"].iloc[0])

                match = None

                for key in mapping_dict:
                    if company.startswith(key) or key in company:
                        match = mapping_dict[key]
                        break

                if match:
                    df["INDUSTRY"] = match["industry"]
                    df["SECTOR"] = match["sector"]
                else:
                    df["INDUSTRY"] = "UNKNOWN"
                    df["SECTOR"] = "UNKNOWN"
                    missing.append(symbol)

            else:
                df["INDUSTRY"] = "UNKNOWN"
                df["SECTOR"] = "UNKNOWN"
                missing.append(symbol)

        # -----------------------------------
        # SAVE
        # -----------------------------------

        df.to_csv(path, index=False)

        print("✔", symbol)

# -----------------------------------
# REPORT
# -----------------------------------

print("\n==============================")
print("📊 FINAL REPORT")
print("==============================")

print("Missing examples:", list(set(missing))[:20])
print("Total missing:", len(set(missing)))

print("\n🔥 FINAL MAPPING COMPLETE")