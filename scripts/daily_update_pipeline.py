import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

def run_script(name, script_name):
    print(f"\n📊 {name}...")
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR)
    if result.returncode == 0:
        print(f"✅ {name} completed")
    else:
        print(f"❌ ERROR in {name} (exit code {result.returncode})")

print("🚀 DAILY UPDATE STARTED")

run_script("Updating industry phases", "generate_industry_phase_history.py")
run_script("Updating industry leaders", "generate_historical_leaders_final.py")
run_script("Updating cycle probabilities", "industry_cycle_prediction_by_industry.py")
run_script("Building master dashboard", "master_dashboard_pro.py")

print("\n🔥 DAILY UPDATE COMPLETE")
