import io
import os
import zipfile
from datetime import datetime, timedelta

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
save_folder = os.path.join(BASE_DIR, "data", "nse_bhavcopy")

os.makedirs(save_folder, exist_ok=True)

print("Updating NSE bhavcopy folder:", save_folder)

headers = {
    "User-Agent": "Mozilla/5.0"
}

def bhavcopy_date(filename):
    date_str = filename.split("_")[-1].replace(".csv", "")
    return datetime.strptime(date_str, "%d%m%Y")


# Start from last downloaded file
files = [f for f in os.listdir(save_folder) if f.endswith(".csv")]

if files:

    last_file = max(files, key=bhavcopy_date)

    start_date = bhavcopy_date(last_file) + timedelta(days=1)

else:
    
    # if folder empty start from 2019
    start_date = datetime(2019,1,1)

end_date = datetime.today()

date = start_date

while date <= end_date:
    
    date_str = date.strftime("%d%m%Y")
    date_alpha = date.strftime("%d%b%Y").upper()
    
    filename = f"sec_bhavdata_full_{date_str}.csv"
    
    # NSE serves bhavcopy as zip files
    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{date.strftime('%Y')}/{date.strftime('%b').upper()}/cm{date_alpha}bhav.csv.zip"
    
    file_path = os.path.join(save_folder, filename)

    # skip if already downloaded
    if os.path.exists(file_path):
        date += timedelta(days=1)
        continue

    try:
        
        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code == 200:
            # Response is a zip file - extract CSV
            try:
                with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                    csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                    csv_data = zf.read(csv_name)
                    with open(file_path, "wb") as f:
                        f.write(csv_data)
                print("Downloaded & extracted:", filename)
            except zipfile.BadZipFile:
                # Fallback: try direct CSV download (some dates may not be zipped)
                if b"SYMBOL" in r.content:
                    with open(file_path, "wb") as f:
                        f.write(r.content)
                    print("Downloaded (csv):", filename)
        else:
            # weekend or holiday
            pass

    except Exception as e:
        
        print("Error:", filename, str(e)[:50])

    date += timedelta(days=1)

print("NSE bhavcopy update completed")
