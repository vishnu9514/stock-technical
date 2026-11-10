"""Refresh NSE data, calculate multi-timeframe MACD, and validate coverage."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BASE_DIR / "scripts"
PIPELINE = [
    ("Update NSE Bhavcopy", "update_nse_bhavcopy.py"),
    ("Update individual daily databases", "update_nse_database.py"),
    ("Resolve and validate ISIN mappings", "validate_isin_mappings.py"),
    ("Build closed weekly, monthly, and quarterly databases", "build_timeframes_fixed.py"),
    ("Calculate MACD for D/W/M/3M", "calculate_macd_all_timeframes.py"),
    ("Build MACD dashboard and data-quality reports", "build_macd_dashboard.py"),
    ("Validate coverage, ISINs, and independent MACD references", "validate_macd_data.py"),
]


def main() -> int:
    start = time.monotonic()
    completed: list[str] = []
    print("\n" + "=" * 72)
    print("NSE MACD pipeline")
    print("=" * 72)
    for index, (name, script_name) in enumerate(PIPELINE, start=1):
        script = SCRIPTS_DIR / script_name
        if not script.is_file():
            print(f"FAILED: {name}; script not found: {script}")
            return 1
        print(f"\n[{index}/{len(PIPELINE)}] {name}")
        result = subprocess.run([sys.executable, str(script)], cwd=BASE_DIR)
        if result.returncode:
            print(f"\nFAILED: {name} (exit code {result.returncode})")
            print(f"Completed before failure: {', '.join(completed) or 'none'}")
            return result.returncode
        completed.append(name)
    elapsed = time.monotonic() - start
    print("\n" + "=" * 72)
    print(f"MACD pipeline passed in {elapsed:.1f} seconds.")
    print(f"Completed: {', '.join(completed)}")
    print(f"Dashboard: {BASE_DIR / 'data' / 'macd_dashboard.csv'}")
    print(f"Coverage report: {BASE_DIR / 'data' / 'stock_coverage_report.csv'}")
    print(f"Quality report: {BASE_DIR / 'data' / 'macd_data_quality_report.csv'}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
