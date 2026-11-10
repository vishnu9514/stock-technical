import pandas as pd
import pytest

from scripts.build_timeframes_fixed import resample_safe
from scripts.calculate_macd_all_timeframes import add_macd
from scripts.isin_mapping import (
    clean_isin,
    load_isin_from_stock_database,
    normalize_columns,
    normalize_symbol,
    resolve_isin,
    validate_isin,
    validate_symbol_isin_mapping,
)
from scripts.update_nse_database import load_bhavcopy_records, update_stock_file
from scripts import validate_macd_data


VALID_ISIN = "INE144J01027"


def test_symbol_and_isin_normalization_and_checksum(tmp_path):
    assert normalize_symbol(" 20microns-EQ ") == "20MICRONS"
    assert normalize_symbol("reliance.NS") == "RELIANCE"
    assert normalize_symbol("abc.bo") == "ABC"
    assert clean_isin(" ine144j01027 ") == VALID_ISIN
    assert validate_isin(VALID_ISIN)
    assert not validate_isin("INE144J01028")

    database = tmp_path / "stock.csv"
    database.write_text(f"DATE,CLOSE,ISIN\n2026-01-01,10,{VALID_ISIN}\n", encoding="utf-8")
    assert load_isin_from_stock_database(database) == {VALID_ISIN}


def test_udiff_headers_are_normalized():
    frame = pd.DataFrame(
        columns=["TckrSymb", "SctySrs", "TradDt", "OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol"]
    )
    assert set(normalize_columns(frame).columns) == {
        "SYMBOL", "SERIES", "DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"
    }


def test_isin_resolution_prioritizes_stock_db_and_reports_conflict():
    value, source, status, conflicts = resolve_isin(
        "20MICRONS",
        {"20MICRONS": {VALID_ISIN}},
        {"20MICRONS": {"INE002A01018"}},
        {},
    )
    assert (value, source, status) == (VALID_ISIN, "stock_database", "VALID_WITH_CONFLICT")
    assert conflicts[0]["SOURCE"] == "bhavcopy"


def test_multiple_source_isins_do_not_select_arbitrarily():
    value, source, status, conflicts = resolve_isin(
        "ABC",
        {"ABC": {VALID_ISIN, "INE002A01018"}},
        {},
        {},
    )
    assert (value, source, status) == ("UNKNOWN", "UNKNOWN", "UNKNOWN")
    assert len(conflicts) == 2


def test_duplicate_isin_across_symbols_is_reported():
    conflicts = validate_symbol_isin_mapping({"AAA": VALID_ISIN, "BBB": VALID_ISIN})
    assert {row["SYMBOL"] for row in conflicts} == {"AAA", "BBB"}


def test_resampler_excludes_incomplete_periods_and_preserves_isin():
    frame = pd.DataFrame(
        [
            ("2026-10-30", 10, 12, 9, 11, 100, VALID_ISIN),
            ("2026-11-06", 11, 14, 10, 13, 200, VALID_ISIN),
            ("2026-11-09", 13, 15, 12, 14, 300, VALID_ISIN),
        ],
        columns=["DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "ISIN"],
    )
    weekly = resample_safe(frame, "W-FRI", pd.Timestamp("2026-11-09"))
    monthly = resample_safe(frame, "ME", pd.Timestamp("2026-11-09"))
    assert weekly["DATE"].dt.strftime("%Y-%m-%d").tolist() == ["2026-10-30", "2026-11-06"]
    assert monthly["DATE"].dt.strftime("%Y-%m-%d").tolist() == ["2026-10-31"]
    assert set(weekly["ISIN"]) == {VALID_ISIN}
    assert weekly.iloc[0]["OPEN"] == 10
    assert weekly.iloc[0]["CLOSE"] == 11


def test_resampler_rejects_conflicting_isins():
    frame = pd.DataFrame(
        [
            ("2026-01-02", 10, 12, 9, 11, 100, VALID_ISIN),
            ("2026-01-05", 11, 14, 10, 13, 200, "INE002A01018"),
        ],
        columns=["DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "ISIN"],
    )
    with pytest.raises(ValueError, match="conflicting valid ISINs"):
        resample_safe(frame, "W-FRI", pd.Timestamp("2026-01-09"))


def test_macd_uses_standard_12_26_9_formula():
    frame = pd.DataFrame({"CLOSE": [float(value) for value in range(1, 50)]})
    result = add_macd(frame)
    expected_12 = frame["CLOSE"].ewm(span=12, adjust=False).mean()
    expected_26 = frame["CLOSE"].ewm(span=26, adjust=False).mean()
    expected_macd = expected_12 - expected_26
    expected_signal = expected_macd.ewm(span=9, adjust=False).mean()
    pd.testing.assert_series_equal(result["MACD"], expected_macd, check_names=False)
    pd.testing.assert_series_equal(result["MACD_SIGNAL"], expected_signal, check_names=False)
    pd.testing.assert_series_equal(result["MACD_HIST"], expected_macd - expected_signal, check_names=False)


def test_validator_accepts_no_data_for_insufficient_quarterly_history(tmp_path, monkeypatch):
    source_dir = tmp_path / "quarterly"
    source_dir.mkdir()
    dates = pd.date_range("2020-03-31", periods=29, freq="QE")
    pd.DataFrame({"DATE": dates, "CLOSE": range(100, 129)}).to_csv(
        source_dir / "ABC.csv", index=False
    )
    monkeypatch.setitem(validate_macd_data.TIMEFRAME_INPUTS, "3M", source_dir)
    row = {
        "3M_MACD_LINE": "",
        "3M_MACD_SIGNAL_LINE": "",
        "3M_MACD_HISTOGRAM": "",
        "3M_MACD_CROSSOVER": "NO_DATA",
    }

    assert not validate_macd_data._check_macd(row, "ABC", "3M")
    row["3M_MACD_CROSSOVER"] = "Bullish"
    with pytest.raises(RuntimeError, match="insufficient history"):
        validate_macd_data._check_macd(row, "ABC", "3M")


def test_validator_samples_stocks_with_any_available_timeframe():
    rows = {
        "20MICRONS": {"D_MACD_CROSSOVER": "Bullish"},
        **{
            f"STOCK{index:02}": {
                "D_MACD_CROSSOVER": "Bullish",
                "W_MACD_CROSSOVER": "Bullish",
                "M_MACD_CROSSOVER": "NO_DATA",
                "3M_MACD_CROSSOVER": "NO_DATA",
            }
            for index in range(20)
        },
        "EMPTY": {
            "D_MACD_CROSSOVER": "NO_DATA",
            "W_MACD_CROSSOVER": "NO_DATA",
            "M_MACD_CROSSOVER": "NO_DATA",
            "3M_MACD_CROSSOVER": "NO_DATA",
        },
    }

    sample = validate_macd_data._select_random_symbols(rows)

    assert len(sample) == 20
    assert "20MICRONS" not in sample
    assert "EMPTY" not in sample


def test_stock_update_preserves_existing_prices_and_isin_and_creates_backup(tmp_path):
    stock = tmp_path / "ABC.csv"
    stock.write_text(
        f"DATE,OPEN,HIGH,LOW,CLOSE,VOLUME,ISIN\n2026-01-02,10,12,9,11,100,{VALID_ISIN}\n",
        encoding="utf-8",
    )
    records = [
        {
            "DATE": "2026-01-02",
            "OPEN": 20,
            "HIGH": 22,
            "LOW": 19,
            "CLOSE": 21,
            "VOLUME": 200,
            "ISIN": "INE002A01018",
        },
        {
            "DATE": "2026-01-05",
            "OPEN": 11,
            "HIGH": 13,
            "LOW": 10,
            "CLOSE": 12,
            "VOLUME": 150,
            "ISIN": "INE002A01018",
        },
    ]
    success, added = update_stock_file(
        stock,
        records,
        {"ABC": {"INE002A01018"}},
        {},
    )
    frame = pd.read_csv(stock)
    assert success and added == 1
    assert frame.loc[0, "CLOSE"] == 11
    assert frame.loc[1, "ISIN"] == VALID_ISIN
    assert list(tmp_path.glob("ABC.csv.*.bak"))


def test_empty_stock_database_is_not_a_parse_failure(tmp_path):
    stock = tmp_path / "IIFLWAM.csv"
    stock.write_bytes(b"")
    success, added = update_stock_file(stock, [], {}, {})
    assert success
    assert added == 0


def test_bhavcopy_reader_supports_udiff_and_legacy_without_isin(tmp_path):
    udiff = tmp_path / "new.csv"
    udiff.write_text(
        "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,ISIN\n"
        f"2026-11-06,ABC,EQ,10,12,9,11,100,{VALID_ISIN}\n",
        encoding="utf-8",
    )
    legacy = tmp_path / "sec_bhavdata_full_06112026.csv"
    legacy.write_text(
        "SYMBOL, SERIES, DATE1, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, TTL_TRD_QNTY\n"
        "ABC, EQ, 06-Nov-2026, 11, 13, 10, 12, 150\n",
        encoding="utf-8",
    )
    records, isins, _ = load_bhavcopy_records(tmp_path)
    assert len(records["ABC"]) == 2
    assert isins["ABC"] == {VALID_ISIN}
    udiff_record = next(row for row in records["ABC"] if row["ISIN"] == VALID_ISIN)
    legacy_record = next(row for row in records["ABC"] if row["ISIN"] == "")
    assert udiff_record["DATE"] == pd.Timestamp("2026-11-06")
    assert legacy_record["DATE"] == pd.Timestamp("2026-11-06")
