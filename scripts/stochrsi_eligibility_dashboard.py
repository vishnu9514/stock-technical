import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Folders
daily_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
weekly_folder = os.path.join(BASE_DIR, "data", "nse_weekly")
monthly_folder = os.path.join(BASE_DIR, "data", "nse_monthly")

# Output file
output_file = os.path.join(BASE_DIR, "data", "stochrsi_eligibility_dashboard.csv")

# Load ISIN mapping
isin_df = pd.read_csv(os.path.join(BASE_DIR, "data", "EQUITY_L.csv"))
isin_df.columns = isin_df.columns.str.strip()  # Strip leading/trailing spaces
isin_mapping = dict(zip(isin_df['SYMBOL'], isin_df['ISIN NUMBER']))

results = []

# Get list of symbols from monthly folder
files = os.listdir(monthly_folder)

for file in files:
    symbol = file.replace(".csv", "")

    try:
        # Load data
        m_df = pd.read_csv(os.path.join(monthly_folder, file))
        w_df = pd.read_csv(os.path.join(weekly_folder, file))
        d_df = pd.read_csv(os.path.join(daily_folder, file))

        # Get latest values
        if len(m_df) == 0 or len(w_df) == 0 or len(d_df) == 0:
            continue

        m_latest = m_df.iloc[-1]
        w_latest = w_df.iloc[-1]
        d_latest = d_df.iloc[-1]

        # Check conditions
        monthly_eligible = m_latest['K'] < 30 and m_latest['D'] < 30
        if not monthly_eligible:
            continue

        weekly_eligible = w_latest['K'] < 30 and w_latest['D'] < 30
        if not weekly_eligible:
            continue

        daily_eligible = d_latest['K'] < 30 and d_latest['D'] < 30
        if not daily_eligible:
            continue

        # Get ISIN
        isin = isin_mapping.get(symbol, '')

        # Add to results
        results.append({
            "SYMBOL": symbol,
            "ISIN": isin,
            "M_K": round(m_latest['K'], 2),
            "M_D": round(m_latest['D'], 2),
            "W_K": round(w_latest['K'], 2),
            "W_D": round(w_latest['D'], 2),
            "D_K": round(d_latest['K'], 2),
            "D_D": round(d_latest['D'], 2),
            "DATE": d_latest['DATE']  # Assuming daily has the most recent date
        })

    except Exception as e:
        continue

# Create DataFrame and save
df = pd.DataFrame(results)
df = df.sort_values("SYMBOL")
df = df[df['ISIN'] != '']  # Filter only those with ISIN
df.to_csv(output_file, index=False)

print(f"✅ StochRSI Eligibility Dashboard created: {output_file}")
print(f"Total eligible stocks with ISIN: {len(df)}")
print("\nEligible Stocks with ISIN:")
print(df.to_string(index=False))