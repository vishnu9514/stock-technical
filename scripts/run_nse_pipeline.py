import subprocess
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

scripts = [
    "update_nse_bhavcopy.py",
    "update_nse_database.py",
    "build_timeframes_fixed.py",
    "calculate_stochrsi_all_timeframes.py",
    "build_indicator_dashboard.py",
    "scan_monthly_momentum.py",
    "map_isin_company_only.py",
]

print("\n🚀 NSE STOCK PIPELINE STARTED\n")

for script in scripts:

    script_path = os.path.join(BASE_DIR, "scripts", script)

    print("Running:", script)

    try:

        subprocess.run(
            [sys.executable, script_path],
            check=True
        )

    except subprocess.CalledProcessError:

        print("❌ Error in:", script)
        sys.exit(1)

    print("✅ Finished:", script)
    print("-" * 50)


print("\n🎯 PIPELINE COMPLETED SUCCESSFULLY\n")