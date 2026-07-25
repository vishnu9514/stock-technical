from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "data" / "supertrend_tv_results.xlsx"

EXPORT_SHEETS: list[tuple[str, Path]] = [
    ("mwd_signals", BASE_DIR / "data" / "supertrend_tv_mwd_signals.csv"),
    ("dashboard", BASE_DIR / "data" / "supertrend_tv_dashboard.csv"),
    ("all_tf_dash", BASE_DIR / "data" / "supertrend_tv_all_timeframes_dashboard.csv"),
    ("bt_summary_5y", BASE_DIR / "data" / "supertrend_tv_backtest_summary_5y.csv"),
    ("bt_trades_5y", BASE_DIR / "data" / "supertrend_tv_backtest_trades_5y.csv"),
    ("bt_yearly_5y", BASE_DIR / "data" / "supertrend_tv_backtest_yearly_5y.csv"),
    ("bt_summary_2y", BASE_DIR / "data" / "supertrend_tv_backtest_summary_recent_2y.csv"),
    ("bt_trades_2y", BASE_DIR / "data" / "supertrend_tv_backtest_recent_2y.csv"),
    ("overall_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_overall_summary_5y.csv"),
    ("tf_summary_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_timeframe_summary_5y.csv"),
    ("yearly_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_yearly_statement_5y.csv"),
    ("quarterly_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_quarterly_statement_5y.csv"),
    ("monthly_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_monthly_statement_5y.csv"),
    ("weekly_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_weekly_statement_5y.csv"),
    ("daily_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_daily_statement_5y.csv"),
    ("stock_5y", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_stock_summary_5y.csv"),
    ("trades_all_tf", BASE_DIR / "data" / "backtests" / "supertrend_tv_5y" / "supertrend_tv_trades_5y_all_timeframes.csv"),
]


def fit_columns(worksheet) -> None:
    for idx, column_cells in enumerate(worksheet.columns, start=1):
        values = ["" if cell.value is None else str(cell.value) for cell in column_cells[:200]]
        max_len = max(len(value) for value in values) if values else 0
        worksheet.column_dimensions[get_column_letter(idx)].width = min(max(max_len + 2, 12), 28)


def style_sheet(worksheet) -> None:
    worksheet.freeze_panes = "A2"
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
    fit_columns(worksheet)


def export_workbook() -> Path:
    available_sheets = [(sheet, path) for sheet, path in EXPORT_SHEETS if path.exists()]
    if not available_sheets:
        raise FileNotFoundError("No Supertrend CSV files were found to export.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        for sheet_name, csv_path in available_sheets:
            df = pd.read_csv(csv_path)
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            style_sheet(writer.book[sheet_name[:31]])

    return OUTPUT_FILE


def main() -> None:
    output_path = export_workbook()
    print(f"Spreadsheet created: {output_path}")


if __name__ == "__main__":
    main()
