import pandas as pd
import os

# -----------------------------
# 1. FILE PATH SETUP
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
file_path = os.path.join(BASE_DIR, "data", "industry_master.csv")

print(f"📂 Loading file from: {file_path}")

# -----------------------------
# 2. LOAD DATA
# -----------------------------
df = pd.read_csv(file_path)

# -----------------------------
# 3. CLEAN COLUMN NAMES
# -----------------------------
df.columns = df.columns.str.strip().str.lower()
print("🧾 Columns found:", df.columns.tolist())

# -----------------------------
# 4. AUTO DETECT INDUSTRY COLUMN
# -----------------------------
industry_col = None

for col in df.columns:
    if "industry" in col:
        industry_col = col
        break

if industry_col is None:
    raise Exception("❌ No industry column found. Check your CSV.")

print(f"✅ Using column: {industry_col}")

# Standardize column
df["industry"] = df[industry_col].astype(str).str.strip().str.lower()

# -----------------------------
# 5. SECTOR MAPPING FUNCTION
# -----------------------------
def map_sector(ind):
    ind = ind.lower()

    if any(x in ind for x in ["bank", "nbfc", "finance", "insurance"]):
        return "Banking & Financial Services"

    elif any(x in ind for x in ["it", "software", "tech", "saas", "cloud"]):
        return "IT & Software"

    elif any(x in ind for x in ["pharma", "hospital", "health", "biotech", "diagnostic"]):
        return "Pharma & Healthcare"

    elif any(x in ind for x in ["auto", "vehicle", "tyre", "battery", "ev"]):
        return "Automobile & EV"

    elif any(x in ind for x in ["fmcg", "food", "beverage", "consumer"]):
        return "FMCG & Consumer Goods"

    elif any(x in ind for x in ["steel", "metal", "mining", "aluminium", "copper"]):
        return "Metals & Mining"

    elif any(x in ind for x in ["oil", "gas", "power", "energy", "coal"]):
        return "Energy"

    elif any(x in ind for x in ["infra", "construction", "cement", "real estate"]):
        return "Infrastructure & Construction"

    elif any(x in ind for x in ["capital goods", "machinery", "engineering", "electrical"]):
        return "Capital Goods / Industrials"

    elif any(x in ind for x in ["chemical", "fertilizer", "paint", "petrochemical"]):
        return "Chemicals"

    elif any(x in ind for x in ["textile", "garment", "fabric"]):
        return "Textiles"

    elif any(x in ind for x in ["telecom", "media", "broadcast"]):
        return "Telecom & Media"

    elif any(x in ind for x in ["retail", "ecommerce", "shopping"]):
        return "Retail & E-commerce"

    elif any(x in ind for x in ["agro", "seed", "sugar", "plantation"]):
        return "Agriculture & Allied"

    elif any(x in ind for x in ["logistics", "shipping", "transport", "airline", "rail"]):
        return "Logistics & Transportation"

    elif any(x in ind for x in ["hotel", "restaurant", "tourism"]):
        return "Hospitality & Services"

    else:
        return "Miscellaneous"

# -----------------------------
# 6. APPLY MAPPING
# -----------------------------
df["sector"] = df["industry"].apply(map_sector)

# -----------------------------
# 7. CHECK UNMAPPED
# -----------------------------
unmapped = df[df["sector"] == "Miscellaneous"]["industry"].unique()

print("\n📊 Total Industries:", df["industry"].nunique())
print("⚠️ Unmapped Industries:", len(unmapped))

if len(unmapped) > 0:
    print("🔍 Unmapped List:")
    for i in unmapped:
        print(" -", i)

# -----------------------------
# 8. SAVE OUTPUT
# -----------------------------
output_path = os.path.join(BASE_DIR, "data", "industry_with_sector.csv")
df.to_csv(output_path, index=False)

print(f"\n✅ Mapping completed. Saved to: {output_path}")