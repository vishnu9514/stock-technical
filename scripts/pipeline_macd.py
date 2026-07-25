"""
Pipeline: Update NSE Bhavcopy → Build Timeframes → Calculate MACD + Elliott Wave
"""
import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

PIPELINE = [
    ("1. Download latest bhavcopy",                "update_nse_bhavcopy.py"),
    ("2. Update NSE stock database",               "update_nse_database.py"),
    ("3. Update volume from bhavcopy",             "update_nse_with_volume_final.py"),
    ("4. Build D/W/M/Q timeframes",                "build_timeframes_fixed.py"),
    ("5. Calculate StochRSI all TF",               "calculate_stochrsi_all_timeframes.py"),
    ("6. Calculate MACD all TF",                   "calculate_macd_all_timeframes.py"),
    ("7. Build MACD dashboard",                    "build_macd_dashboard.py"),
    ("8. Calculate Elliott Trendline all TF",      "elliott_trendline_all_timeframes.py"),
    ("9. Build Elliott dashboard",                 "build_elliott_dashboard.py"),
    ("10. Backtest accumulation to markup",        "backtest_accumulation_to_markup.py"),
    ("11. Backtest accumulation markup leaders",   "backtest_accumulation_markup_leaders_only.py"),
    ("12. Backtest leader hold real",              "backtest_leader_hold_real.py"),
    ("13. Backtest main industry leaders",         "backtest_main_industry_leaders_final.py"),
]


def run():
    print("\n" + "=" * 60)
    print("  🚀 PIPELINE 4: BHAVCOPY → MACD + ELLIOTT")
    print("=" * 60)

    for step_name, script in PIPELINE:
        script_path = os.path.join(SCRIPTS_DIR, script)
        print(f"\n▶ {step_name} ({script})")
        result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR)
        if result.returncode != 0:
            print(f"❌ FAILED at step: {step_name}")
            sys.exit(1)
        print(f"✅ {step_name} completed")

    print("\n" + "=" * 60)
    print("  ✅ PIPELINE 4 COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    run()