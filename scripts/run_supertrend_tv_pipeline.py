import argparse
import os
import subprocess
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

PIPELINE_SCRIPTS = [
    "update_nse_bhavcopy.py",
    "update_nse_database.py",
    "update_nse_with_volume_final.py",
    "build_timeframes_fixed.py",
    "calculate_stochrsi_all_timeframes.py",
    "add_main_industry_all_timeframes.py",
]

DASHBOARD_SCRIPT = "supertrend_tv_dashboard_final.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full Supertrend TV data pipeline and dashboard build."
    )
    parser.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Skip upstream refresh scripts and rebuild only the dashboard from existing data.",
    )
    return parser.parse_args()


def run_script(script_name: str, extra_args: list[str] | None = None) -> None:
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    command = [sys.executable, script_path]
    if extra_args:
        command.extend(extra_args)

    print(f"\n=== Running: {script_name} ===")
    subprocess.run(command, cwd=BASE_DIR, check=True)


def main() -> None:
    args = parse_args()

    print("\n=== SUPERTREND TV PIPELINE STARTED ===")

    if not args.dashboard_only:
        for script_name in PIPELINE_SCRIPTS:
            run_script(script_name)

    run_script(DASHBOARD_SCRIPT, ["--skip-pipeline"])

    print("\n=== SUPERTREND TV PIPELINE COMPLETED ===")


if __name__ == "__main__":
    main()
