import os
import shutil
import datetime
import requests
import zipfile

# -----------------------------------
# BASE PATH (FIXED)
# -----------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data", "nse_stocks")
BHAV_DIR = os.path.join(BASE_DIR, "data", "nse_bhavcopy")
BACKUP_DIR = os.path.join(BASE_DIR, "data", "backup_nse_stocks")

os.makedirs(BHAV_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

print("\n🚀 FULLY AUTOMATED MAIN INDUSTRY PIPELINE STARTED\n")
print("📁 BASE DIR:", BASE_DIR)

# -----------------------------------
# STEP 0: BACKUP
# -----------------------------------

try:
    if os.path.exists(DATA_DIR):
        today = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        backup_path = os.path.join(BACKUP_DIR, f"backup_{today}")
        shutil.copytree(DATA_DIR, backup_path, dirs_exist_ok=True)
        print(f"✅ Backup created → {backup_path}")
    else:
        print("⚠️ No nse_stocks folder found (skip backup)")
except Exception as e:
    print("⚠️ Backup failed:", e)

# -----------------------------------
# STEP 1: DOWNLOAD BHAVCOPY
# -----------------------------------

def download_bhavcopy():
    today = datetime.datetime.now()

    date_str = today.strftime("%d%b%Y").upper()
    year = today.strftime("%Y")
    month = today.strftime("%b").upper()

    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{date_str}bhav.csv.zip"

    zip_path = os.path.join(BHAV_DIR, f"{date_str}.zip")

    if os.path.exists(zip_path):
        print("ℹ️ Bhavcopy already exists (skip download)")
        return

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 200:
            with open(zip_path, "wb") as f:
                f.write(r.content)

            print("✅ Bhavcopy downloaded")

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(BHAV_DIR)

            print("✅ Bhavcopy extracted")

        else:
            print("⚠️ Bhavcopy not available today (market closed?)")

    except Exception as e:
        print("⚠️ Download error:", e)

download_bhavcopy()

# -----------------------------------
# HELPER FUNCTION
# -----------------------------------

def run_step(name, command):
    print(f"\n🔹 {name}...")
    result = os.system(command)

    if result != 0:
        print(f"❌ ERROR in {name}")
    else:
        print(f"✅ {name} completed")

# -----------------------------------
# STEP 2: UPDATE NSE DATABASE
# -----------------------------------

run_step(
    "Updating NSE database with bhavcopy",
    f'python scripts/update_nse_with_volume.py "{BHAV_DIR}"'
)

# -----------------------------------
# STEP 3: BUILD TIMEFRAMES
# -----------------------------------

run_step(
    "Building timeframes (D/W/M/Q)",
    "python scripts/build_timeframes.py"
)

# -----------------------------------
# STEP 4: STOCHRSI
# -----------------------------------

run_step(
    "Calculating StochRSI",
    "python scripts/add_stochrsi_all_tf.py"
)

# -----------------------------------
# STEP 5: MAIN INDUSTRY MAPPING
# -----------------------------------

run_step(
    "Mapping MAIN INDUSTRY",
    "python scripts/map_main_industry_only.py"
)

# -----------------------------------
# STEP 6: MAIN INDUSTRY PHASE
# -----------------------------------

run_step(
    "Generating MAIN INDUSTRY phases",
    "python scripts/generate_main_industry_phase.py"
)

# -----------------------------------
# STEP 7: LEADERS
# -----------------------------------

run_step(
    "Generating MAIN INDUSTRY leaders",
    "python scripts/generate_main_industry_leaders.py"
)

# -----------------------------------
# STEP 8: PROBABILITY
# -----------------------------------

run_step(
    "Generating cycle probabilities",
    "python scripts/main_industry_cycle_probability.py"
)

# -----------------------------------
# STEP 9: DASHBOARD
# -----------------------------------

run_step(
    "Building MASTER dashboard",
    "python scripts/master_dashboard_main_industry.py"
)

# -----------------------------------
# DONE
# -----------------------------------

print("\n==============================")
print("🔥 FULL PIPELINE COMPLETED")
print("==============================\n")