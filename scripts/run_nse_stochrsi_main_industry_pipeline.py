import subprocess
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

scripts = [
    "update_nse_bhavcopy.py",
    "update_nse_database.py",
    "build_timeframes_fixed.py",
    "calculate_stochrsi_all_timeframes.py",
    "add_main_industry_all_timeframes.py",
]

print("\n🚀 NSE -> DATABASE -> STOCHRSI -> MAIN INDUSTRY PIPELINE STARTED\n")

for script in scripts:
    script_path = os.path.join(BASE_DIR, "scripts", script)
    print(f"Running: {script}")

    try:
        subprocess.run([sys.executable, script_path], check=True)
    except subprocess.CalledProcessError:
        print(f"❌ Error in: {script}")
        sys.exit(1)

    print(f"✅ Finished: {script}")
    print("-" * 50)

print("\n🎯 PIPELINE COMPLETED SUCCESSFULLY\n")
