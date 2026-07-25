"""
Pipeline: Update NSE Bhavcopy → Build Timeframes → Calculate SuperTrend TV + Dashboard
"""
import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

PIPELINE = [
    ("1. Download latest bhavcopy",           "update_nse_bhavcopy.py"),
    ("2. Update NSE stock database",          "update_nse_database.py"),
    ("3. Update volume from bhavcopy",        "update_nse_with_volume_final.py"),
    ("4. Build D/W/M/Q timeframes",           "build_timeframes_fixed.py"),
    ("5. Calculate StochRSI all TF",          "calculate_stochrsi_all_timeframes.py"),
    ("6. Add main industry mapping",          "add_main_industry_all_timeframes.py"),
    ("7. Calculate SuperTrend TV all TF",     "calculate_supertrend_tv_all_timeframes.py"),
    ("8. Build SuperTrend TV dashboard",      "supertrend_tv_dashboard_final.py"),
    ("9. Export to Excel",                    "export_supertrend_results_to_excel.py"),
    ("10. Backtest SuperTrend TV (5Y)",       "backtest_supertrend_tv_indicator.py"),
]


def run():
    print("\n" + "=" * 60)
    print("  🚀 PIPELINE 2: BHAVCOPY → SUPERTREND TV")
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
    print("  ✅ PIPELINE 2 COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    run()