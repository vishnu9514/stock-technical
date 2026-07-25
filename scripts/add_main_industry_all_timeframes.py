import os

import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING_FILE = os.path.join(BASE_DIR, "data", "main industries.xlsx")
FOLDERS = [
    "nse_stocks",
    "nse_weekly",
    "nse_monthly",
    "nse_quarterly",
]


def clean_symbol(value: str) -> str:
    return (
        str(value)
        .upper()
        .strip()
        .replace(".NS", "")
        .replace("-EQ", "")
        .replace(".BO", "")
    )


def load_main_industry_map() -> dict:
    mapping_df = pd.read_excel(MAPPING_FILE)
    mapping_df.columns = mapping_df.columns.str.strip().str.upper()

    symbol_col = next((column for column in mapping_df.columns if "SYMBOL" in column), None)
    main_industry_col = next((column for column in mapping_df.columns if "MAIN_INDUSTRY" in column), None)

    if symbol_col is None or main_industry_col is None:
        raise ValueError("Could not detect SYMBOL / MAIN_INDUSTRY columns in mapping file")

    mapping_df["SYMBOL_KEY"] = mapping_df[symbol_col].apply(clean_symbol)
    mapping_df["MAIN_INDUSTRY_VALUE"] = mapping_df[main_industry_col].astype(str).str.strip()
    mapping_df = mapping_df.drop_duplicates(subset=["SYMBOL_KEY"], keep="first")

    return mapping_df.set_index("SYMBOL_KEY")["MAIN_INDUSTRY_VALUE"].to_dict()


def main() -> None:
    if not os.path.exists(MAPPING_FILE):
        raise FileNotFoundError(f"Mapping file not found: {MAPPING_FILE}")

    mapping = load_main_industry_map()
    print(f"Loaded MAIN_INDUSTRY mappings: {len(mapping):,}")

    for folder in FOLDERS:
        folder_path = os.path.join(BASE_DIR, "data", folder)
        if not os.path.exists(folder_path):
            print(f"Skipping missing folder: {folder_path}")
            continue

        updated = 0
        files = [file for file in os.listdir(folder_path) if file.lower().endswith(".csv")]
        print(f"Processing {folder}: {len(files):,} files")

        for file in files:
            symbol = clean_symbol(os.path.splitext(file)[0])
            path = os.path.join(folder_path, file)

            try:
                df = pd.read_csv(path)
            except Exception:
                continue

            df["MAIN_INDUSTRY"] = mapping.get(symbol, "UNKNOWN")
            df.to_csv(path, index=False)
            updated += 1

        print(f"Updated {updated:,} files in {folder}")

    print("MAIN_INDUSTRY added to all timeframes")


if __name__ == "__main__":
    main()
