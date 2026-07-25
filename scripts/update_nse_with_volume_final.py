import os

import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BHAV_FOLDER = os.path.join(BASE_DIR, "data", "nse_bhavcopy")
DAILY_FOLDER = os.path.join(BASE_DIR, "data", "nse_stocks")
TIMEFRAME_FOLDERS = {
    "W": os.path.join(BASE_DIR, "data", "nse_weekly"),
    "M": os.path.join(BASE_DIR, "data", "nse_monthly"),
    "3M": os.path.join(BASE_DIR, "data", "nse_quarterly"),
}
RESAMPLE_RULES = {
    "W": "W",
    "M": "ME",
    "3M": "QE",
}


def load_bhavcopy_volume():
    if not os.path.exists(BHAV_FOLDER):
        raise FileNotFoundError(f"Folder not found: {BHAV_FOLDER}")

    print("Loading NSE bhavcopy volume...")

    frames = []

    for file in os.listdir(BHAV_FOLDER):
        if not file.lower().endswith(".csv"):
            continue

        path = os.path.join(BHAV_FOLDER, file)

        try:
            df = pd.read_csv(path)
        except Exception:
            continue

        df.columns = df.columns.str.strip()

        required = {"SYMBOL", "DATE1", "TTL_TRD_QNTY"}
        if not required.issubset(df.columns):
            continue

        if "SERIES" in df.columns:
            df["SERIES"] = df["SERIES"].astype(str).str.strip()
            df = df[df["SERIES"] == "EQ"]

        df = df[["SYMBOL", "DATE1", "TTL_TRD_QNTY"]].copy()
        df["SYMBOL"] = df["SYMBOL"].astype(str).str.upper().str.strip()
        df["DATE"] = pd.to_datetime(df["DATE1"], errors="coerce")
        df["BHAV_VOLUME"] = pd.to_numeric(df["TTL_TRD_QNTY"], errors="coerce")
        df = df.dropna(subset=["DATE", "BHAV_VOLUME"])
        frames.append(df[["SYMBOL", "DATE", "BHAV_VOLUME"]])

    if not frames:
        raise RuntimeError("No valid bhavcopy files found")

    bhav = pd.concat(frames, ignore_index=True)
    bhav = bhav.drop_duplicates(subset=["SYMBOL", "DATE"], keep="last")

    print(f"Loaded {len(bhav):,} symbol/date volume rows")
    return {symbol: group[["DATE", "BHAV_VOLUME"]] for symbol, group in bhav.groupby("SYMBOL")}


def update_daily_volume(file, bhav_by_symbol):
    symbol = os.path.splitext(file)[0].upper()
    path = os.path.join(DAILY_FOLDER, file)

    try:
        df = pd.read_csv(path)
    except Exception:
        return False, False

    if "DATE" not in df.columns:
        return False, False

    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")

    if "VOLUME" not in df.columns:
        df["VOLUME"] = pd.NA

    df["VOLUME"] = pd.to_numeric(df["VOLUME"], errors="coerce")

    bhav_volume = bhav_by_symbol.get(symbol)
    matched = False

    if bhav_volume is not None and not bhav_volume.empty:
        before = df["VOLUME"].copy()
        df = df.merge(bhav_volume, on="DATE", how="left")
        df["VOLUME"] = df["BHAV_VOLUME"].combine_first(df["VOLUME"]).fillna(0)
        df = df.drop(columns=["BHAV_VOLUME"])
        matched = not before.equals(df["VOLUME"])
    else:
        df["VOLUME"] = df["VOLUME"].fillna(0)

    df = df.sort_values("DATE")
    df.to_csv(path, index=False)

    return True, matched


def build_resampled_volume(daily_df, rule):
    if "DATE" not in daily_df.columns or "VOLUME" not in daily_df.columns:
        return pd.DataFrame(columns=["DATE", "NEW_VOLUME"])

    volume = daily_df[["DATE", "VOLUME"]].copy()
    volume["DATE"] = pd.to_datetime(volume["DATE"], errors="coerce")
    volume["VOLUME"] = pd.to_numeric(volume["VOLUME"], errors="coerce").fillna(0)
    volume = volume.dropna(subset=["DATE"]).set_index("DATE").sort_index()

    return (
        volume.resample(rule)["VOLUME"]
        .sum()
        .reset_index()
        .rename(columns={"VOLUME": "NEW_VOLUME"})
    )


def update_timeframe_volume(file, daily_df):
    updated = 0

    for timeframe, folder in TIMEFRAME_FOLDERS.items():
        path = os.path.join(folder, file)
        if not os.path.exists(path):
            continue

        try:
            tf_df = pd.read_csv(path)
        except Exception:
            continue

        if "DATE" not in tf_df.columns:
            continue

        resampled = build_resampled_volume(daily_df, RESAMPLE_RULES[timeframe])
        if resampled.empty:
            continue

        tf_df["DATE"] = pd.to_datetime(tf_df["DATE"], errors="coerce")

        if "VOLUME" in tf_df.columns:
            tf_df = tf_df.drop(columns=["VOLUME"])

        tf_df = tf_df.merge(resampled, on="DATE", how="left")
        tf_df = tf_df.rename(columns={"NEW_VOLUME": "VOLUME"})
        tf_df["VOLUME"] = pd.to_numeric(tf_df["VOLUME"], errors="coerce").fillna(0)

        tf_df.to_csv(path, index=False)
        updated += 1

    return updated


def main():
    bhav_by_symbol = load_bhavcopy_volume()

    if not os.path.exists(DAILY_FOLDER):
        raise FileNotFoundError(f"Folder not found: {DAILY_FOLDER}")

    daily_files = [file for file in os.listdir(DAILY_FOLDER) if file.lower().endswith(".csv")]

    updated_daily = 0
    matched_daily = 0
    updated_timeframes = 0
    missing_symbols = []

    print("Updating daily and timeframe volume...")

    for index, file in enumerate(daily_files, start=1):
        symbol = os.path.splitext(file)[0].upper()

        if symbol not in bhav_by_symbol:
            missing_symbols.append(symbol)

        processed, matched = update_daily_volume(file, bhav_by_symbol)
        if not processed:
            continue

        updated_daily += 1
        if matched:
            matched_daily += 1

        daily_path = os.path.join(DAILY_FOLDER, file)
        try:
            daily_df = pd.read_csv(daily_path)
        except Exception:
            continue

        updated_timeframes += update_timeframe_volume(file, daily_df)

        if index % 250 == 0 or index == len(daily_files):
            print(f"Processed {index:,}/{len(daily_files):,} symbols")

    print("\nFINAL REPORT")
    print("============")
    print(f"Daily files updated: {updated_daily:,}")
    print(f"Daily files with bhavcopy matches: {matched_daily:,}")
    print(f"Timeframe files updated: {updated_timeframes:,}")
    print(f"Symbols missing in bhavcopy: {len(set(missing_symbols)):,}")
    print(f"Missing examples: {sorted(set(missing_symbols))[:20]}")
    print("\nNSE volume update completed.")


if __name__ == "__main__":
    main()
