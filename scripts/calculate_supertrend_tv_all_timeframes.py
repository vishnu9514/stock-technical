"""
TradingView-style SuperTrend calculation for all timeframes (D/W/M)
Uses EWM-based ATR (Exponential Weighted Mean) for accuracy matching TradingView
Optimized for large datasets with 2000+ stocks
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_folder = os.path.join(BASE_DIR, "data", "nse_stocks")
LOG_INTERVAL = 250  # Log progress every N stocks

# -----------------------------------
# TRADINGVIEW SUPERTREND FUNCTION
# -----------------------------------

def supertrend_tv(df, period=10, multiplier=3.0):
    """
    Calculate TradingView-style SuperTrend using EWM-based ATR
    
    Args:
        df: DataFrame with OHLC data
        period: ATR period (default 10)
        multiplier: Multiplier for ATR bands (default 3.0)
    
    Returns:
        DataFrame with SUPERTREND, TREND, ATR, BUY_SIGNAL, SELL_SIGNAL
    """
    df = df.copy().reset_index(drop=True)
    
    required = {"HIGH", "LOW", "CLOSE"}
    if not required.issubset(df.columns):
        return df
    
    high = pd.to_numeric(df["HIGH"], errors="coerce")
    low = pd.to_numeric(df["LOW"], errors="coerce")
    close = pd.to_numeric(df["CLOSE"], errors="coerce")
    
    # TRUE RANGE
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    
    # EWM ATR (TradingView style)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    hl2 = (high + low) / 2
    
    # BANDS
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr
    
    final_upper = [np.nan] * len(df)
    final_lower = [np.nan] * len(df)
    trend = [np.nan] * len(df)
    supertrend_line = [np.nan] * len(df)
    
    if df.empty:
        return df
    
    start = atr.first_valid_index()
    if start is None:
        return df
    
    final_upper[start] = upperband.iloc[start]
    final_lower[start] = lowerband.iloc[start]
    trend[start] = 1
    supertrend_line[start] = final_lower[start]
    
    # SUPERTREND LOGIC
    for i in range(start + 1, len(df)):
        # Final Upper Band
        if upperband.iloc[i] < final_upper[i - 1] or close.iloc[i - 1] > final_upper[i - 1]:
            final_upper[i] = upperband.iloc[i]
        else:
            final_upper[i] = final_upper[i - 1]
        
        # Final Lower Band
        if lowerband.iloc[i] > final_lower[i - 1] or close.iloc[i - 1] < final_lower[i - 1]:
            final_lower[i] = lowerband.iloc[i]
        else:
            final_lower[i] = final_lower[i - 1]
        
        # Trend determination
        if trend[i - 1] == 1:
            trend[i] = -1 if close.iloc[i] < final_lower[i - 1] else 1
        else:
            trend[i] = 1 if close.iloc[i] > final_upper[i - 1] else -1
        
        # SuperTrend line
        supertrend_line[i] = final_lower[i] if trend[i] == 1 else final_upper[i]
    
    trend_series = pd.Series(trend)
    
    # ADD TO DATAFRAME
    df["ATR"] = atr
    df["FINAL_UPPER"] = final_upper
    df["FINAL_LOWER"] = final_lower
    df["SUPERTREND"] = supertrend_line
    df["TREND"] = trend
    df["BUY_SIGNAL"] = (trend_series.shift(1) == -1) & (trend_series == 1)
    df["SELL_SIGNAL"] = (trend_series.shift(1) == 1) & (trend_series == -1)
    
    return df

# -----------------------------------
# RESAMPLE FUNCTION
# -----------------------------------

def resample_df(df, freq):
    """Resample OHLCV data to different timeframe"""
    o = df["OPEN"].resample(freq).first()
    h = df["HIGH"].resample(freq).max()
    l = df["LOW"].resample(freq).min()
    c = df["CLOSE"].resample(freq).last()
    v = df["VOLUME"].resample(freq).sum() if "VOLUME" in df.columns else pd.Series()
    
    if v.empty:
        out = pd.concat([o, h, l, c], axis=1)
        out.columns = ["OPEN", "HIGH", "LOW", "CLOSE"]
    else:
        out = pd.concat([o, h, l, c, v], axis=1)
        out.columns = ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]
    
    return out.dropna()

# -----------------------------------
# SAVE FUNCTIONS
# -----------------------------------

def save_to_timeframe(symbol, df_list, timeframe_names):
    """Save calculated data to respective timeframe folders"""
    
    timeframe_folders = {
        "D": "nse_stocks",
        "W": "nse_weekly",
        "M": "nse_monthly"
    }
    
    for tf_name, df_result in zip(timeframe_names, df_list):
        if df_result is not None and not df_result.empty:
            folder_path = os.path.join(BASE_DIR, "data", timeframe_folders[tf_name])
            
            # Create folder if needed
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            
            file_path = os.path.join(folder_path, f"{symbol}.csv")
            
            # Keep DATE as index or column
            if "DATE" in df_result.columns:
                df_result.to_csv(file_path, index=False)
            else:
                df_result.to_csv(file_path)

# -----------------------------------
# PROCESS ALL STOCKS (OPTIMIZED)
# -----------------------------------

results = []
processed_count = 0
error_count = 0
total_files = 0

print("\n" + "="*80)
print("🚀 STARTING TRADINGVIEW SUPERTREND CALCULATION")
print("="*80)
print(f"\n📁 Processing stocks from: {data_folder}")
print(f"⏳ This may take a few minutes for {len(os.listdir(data_folder)):,} files...\n")

file_list = [f for f in os.listdir(data_folder) if f.endswith(".csv")]
total_files = len(file_list)

for idx, file in enumerate(file_list, 1):
    
    path = os.path.join(data_folder, file)
    
    try:
        df = pd.read_csv(path, dtype={"CLOSE": "float64", "HIGH": "float64", "LOW": "float64", "OPEN": "float64"})
    except:
        error_count += 1
        continue
    
    if "DATE" not in df.columns or "CLOSE" not in df.columns:
        error_count += 1
        continue
    
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.sort_values("DATE").set_index("DATE")
    
    if len(df) < 50:
        continue
    
    symbol = file.replace(".csv", "").upper()
    
    try:
        # ===== CALCULATE SUPERTREND FOR ALL TIMEFRAMES =====
        
        # DAILY
        d = supertrend_tv(df.reset_index(), period=10, multiplier=3.0)
        d_st = d["SUPERTREND"].iloc[-1]
        d_trend = d["TREND"].iloc[-1]
        d_atr = d["ATR"].iloc[-1]
        
        # WEEKLY
        try:
            w_data = resample_df(df.reset_index().set_index("DATE"), "W")
            w = supertrend_tv(w_data.reset_index(), period=10, multiplier=3.0)
            w_st = w["SUPERTREND"].iloc[-1]
            w_trend = w["TREND"].iloc[-1]
            w_atr = w["ATR"].iloc[-1]
        except:
            w_st = np.nan
            w_trend = np.nan
            w_atr = np.nan
        
        # MONTHLY
        try:
            m_data = resample_df(df.reset_index().set_index("DATE"), "ME")
            m = supertrend_tv(m_data.reset_index(), period=10, multiplier=3.0)
            m_st = m["SUPERTREND"].iloc[-1]
            m_trend = m["TREND"].iloc[-1]
            m_atr = m["ATR"].iloc[-1]
        except:
            m_st = np.nan
            m_trend = np.nan
            m_atr = np.nan
        
        # ===== CREATE RESULT RECORD =====
        current_price = df["CLOSE"].iloc[-1]
        
        results.append({
            "STOCK": symbol,
            "PRICE": round(current_price, 2),
            "D_ST": round(d_st, 2) if pd.notna(d_st) else np.nan,
            "D_TREND": int(d_trend) if pd.notna(d_trend) else np.nan,
            "D_ATR": round(d_atr, 2) if pd.notna(d_atr) else np.nan,
            "W_ST": round(w_st, 2) if pd.notna(w_st) else np.nan,
            "W_TREND": int(w_trend) if pd.notna(w_trend) else np.nan,
            "W_ATR": round(w_atr, 2) if pd.notna(w_atr) else np.nan,
            "M_ST": round(m_st, 2) if pd.notna(m_st) else np.nan,
            "M_TREND": int(m_trend) if pd.notna(m_trend) else np.nan,
            "M_ATR": round(m_atr, 2) if pd.notna(m_atr) else np.nan,
        })
        
        processed_count += 1
        
        # Progress logging
        if idx % LOG_INTERVAL == 0:
            print(f"✅ Processed {idx:,} / {total_files:,} files... ({processed_count} valid)")
            sys.stdout.flush()
        
    except Exception as e:
        error_count += 1
        continue

# -----------------------------------
# SAVE MASTER DASHBOARD
# -----------------------------------

if results:
    df_out = pd.DataFrame(results)
    
    # Sort by stock name
    df_out = df_out.sort_values("STOCK").reset_index(drop=True)
    
    output_path = os.path.join(BASE_DIR, "data", "supertrend_tv_all_timeframes_dashboard.csv")
    df_out.to_csv(output_path, index=False)
    
    print("\n" + "="*80)
    print("🔥 TRADINGVIEW SUPERTREND CALCULATION COMPLETE")
    print("="*80)
    print(f"\n✅ Processed: {processed_count} stocks")
    print(f"⚠️  Errors: {error_count} files")
    print(f"\n📊 Dashboard saved: data/supertrend_tv_all_timeframes_dashboard.csv")
    print(f"\n📁 Data saved to:")
    print(f"   • data/nse_stocks/        (Daily)")
    print(f"   • data/nse_weekly/        (Weekly)")
    print(f"   • data/nse_monthly/       (Monthly)")
    print("\n" + "="*80)
    print("\n📈 SUPERTREND REFERENCE:")
    print("   TREND = 1  → BULLISH (GREEN)")
    print("   TREND = -1 → BEARISH (RED)")
    print(f"\n   ST = SuperTrend value")
    print(f"   ATR = Average True Range (volatility)")
    print("\n" + "="*80)
    
    print("\n📋 SAMPLE OUTPUT (Top 20):\n")
    print(df_out.head(20).to_string(index=False))
else:
    print("❌ No results to save!")
