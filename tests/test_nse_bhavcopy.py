import csv
import io
import zipfile

from scripts.update_nse_bhavcopy import csv_from_response


def test_csv_from_response_normalizes_current_nse_udiff_archive():
    source = (
        "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,ISIN\n"
        "2026-11-04,ABC,EQ,10.00,12.00,9.50,11.50,1234,INE000A01000\n"
    ).encode()
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BhavCopy.csv", source)

    normalized = csv_from_response(archive_bytes.getvalue()).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(normalized)))

    assert rows == [
        {
            "SYMBOL": "ABC",
            "SERIES": "EQ",
            "DATE1": "2026-11-04",
            "OPEN_PRICE": "10.00",
            "HIGH_PRICE": "12.00",
            "LOW_PRICE": "9.50",
            "CLOSE_PRICE": "11.50",
            "TTL_TRD_QNTY": "1234",
            "ISIN": "INE000A01000",
        }
    ]
