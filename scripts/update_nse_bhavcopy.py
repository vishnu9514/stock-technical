import csv
import io
import os
import zipfile
from datetime import datetime, timedelta

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_FOLDER = os.path.join(BASE_DIR, "data", "nse_bhavcopy")

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
}


def bhavcopy_date(filename):
    date_str = filename.split("_")[-1].replace(".csv", "")
    return datetime.strptime(date_str, "%d%m%Y")


def csv_from_response(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            csv_names = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv")
            ]
            if not csv_names:
                raise ValueError("Bhavcopy archive did not contain a CSV")
            content = archive.read(csv_names[0])
    except zipfile.BadZipFile:
        pass

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        columns = {column.strip() for column in (reader.fieldnames or [])}
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("Bhavcopy response has an invalid CSV header") from error

    required_columns = {
        "SYMBOL",
        "SERIES",
        "OPEN_PRICE",
        "HIGH_PRICE",
        "LOW_PRICE",
        "CLOSE_PRICE",
        "TTL_TRD_QNTY",
    }
    udiff_columns = {
        "TradDt",
        "TckrSymb",
        "SctySrs",
        "OpnPric",
        "HghPric",
        "LwPric",
        "ClsPric",
        "TtlTradgVol",
    }
    if udiff_columns.issubset(columns):
        standardized = io.StringIO(newline="")
        output_columns = [
            "SYMBOL",
            "SERIES",
            "DATE1",
            "OPEN_PRICE",
            "HIGH_PRICE",
            "LOW_PRICE",
            "CLOSE_PRICE",
            "TTL_TRD_QNTY",
            "ISIN",
        ]
        writer = csv.DictWriter(standardized, fieldnames=output_columns)
        writer.writeheader()
        for row in reader:
            writer.writerow(
                {
                    "SYMBOL": row.get("TckrSymb", ""),
                    "SERIES": row.get("SctySrs", ""),
                    "DATE1": row.get("TradDt", ""),
                    "OPEN_PRICE": row.get("OpnPric", ""),
                    "HIGH_PRICE": row.get("HghPric", ""),
                    "LOW_PRICE": row.get("LwPric", ""),
                    "CLOSE_PRICE": row.get("ClsPric", ""),
                    "TTL_TRD_QNTY": row.get("TtlTradgVol", ""),
                    "ISIN": row.get("ISIN", ""),
                }
            )
        content = standardized.getvalue().encode("utf-8")
        columns = set(output_columns)

    columns = {column.strip().upper() for column in columns}
    if not required_columns.issubset(columns):
        raise ValueError("Bhavcopy CSV is missing required NSE columns")

    return content


def existing_bhavcopy_dates(folder):
    dates = []
    for filename in os.listdir(folder):
        if not filename.startswith("sec_bhavdata_full_") or not filename.endswith(".csv"):
            continue
        try:
            dates.append(bhavcopy_date(filename))
        except ValueError:
            print(f"Skipping unexpected bhavcopy filename: {filename}")
    return dates


def validate_latest_bhavcopy(latest_date, end_date):
    if latest_date is None:
        raise RuntimeError("No valid NSE bhavcopy files are available")
    if (end_date.date() - latest_date.date()).days > 7:
        raise RuntimeError(
            "NSE bhavcopy data is stale: latest available session is "
            f"{latest_date:%Y-%m-%d}; no recent files were downloaded"
        )


def main():
    os.makedirs(SAVE_FOLDER, exist_ok=True)
    print("Updating NSE bhavcopy folder:", SAVE_FOLDER)

    downloaded_dates = existing_bhavcopy_dates(SAVE_FOLDER)
    if downloaded_dates:
        # Recheck the latest week so missed exchange sessions can be backfilled.
        start_date = max(datetime(2019, 1, 1), max(downloaded_dates) - timedelta(days=7))
    else:
        start_date = datetime(2019, 1, 1)

    end_date = datetime.today()
    date = start_date
    downloaded_count = 0

    with requests.Session() as session:
        while date <= end_date:
            date_str = date.strftime("%d%m%Y")
            filename = f"sec_bhavdata_full_{date_str}.csv"
            file_path = os.path.join(SAVE_FOLDER, filename)

            if os.path.exists(file_path):
                date += timedelta(days=1)
                continue

            url = (
                "https://nsearchives.nseindia.com/content/cm/"
                f"BhavCopy_NSE_CM_0_0_0_{date.strftime('%Y%m%d')}_F_0000.csv.zip"
            )

            try:
                response = session.get(url, headers=headers, timeout=30)
            except requests.RequestException as error:
                raise RuntimeError(f"Failed to download {filename}") from error

            if response.status_code == 200:
                csv_data = csv_from_response(response.content)
                temporary_path = f"{file_path}.tmp"
                with open(temporary_path, "wb") as output_file:
                    output_file.write(csv_data)
                os.replace(temporary_path, file_path)
                downloaded_count += 1
                print("Downloaded:", filename)
            elif response.status_code != 404:
                response.raise_for_status()

            date += timedelta(days=1)

    latest_date = max(existing_bhavcopy_dates(SAVE_FOLDER), default=None)
    validate_latest_bhavcopy(latest_date, end_date)
    print(f"NSE bhavcopy update completed ({downloaded_count:,} new files)")


if __name__ == "__main__":
    main()
