import requests
import os
from datetime import datetime, timedelta

# detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

save_folder = os.path.join(BASE_DIR, "data", "nse_bhavcopy")
os.makedirs(save_folder, exist_ok=True)

print("Saving files to:", save_folder)

# NSE archive reliable from ~2019
start_date = datetime(2019, 1, 1)
end_date = datetime.today()

headers = {
    "User-Agent": "Mozilla/5.0"
}

date = start_date

while date <= end_date:

    date_str = date.strftime("%d%m%Y")

    filename = f"sec_bhavdata_full_{date_str}.csv"

    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{date.strftime('%Y')}/{date.strftime('%b').upper()}/cm{date_str}bhav.csv.zip"

    file_path = os.path.join(save_folder, filename)

    # skip if already downloaded
    if os.path.exists(file_path):
        date += timedelta(days=1)
        continue

    try:

        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code == 200 and "SYMBOL" in r.text:

            with open(file_path, "wb") as f:
                f.write(r.content)

            print("Downloaded:", filename)

        else:
            # weekends / holidays
            pass

    except Exception as e:
        print("Error:", filename)

    date += timedelta(days=1)

print("NSE bhavcopy download completed")