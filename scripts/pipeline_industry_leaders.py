"""
Pipeline: Update NSE Bhavcopy → Build Timeframes → Industry Leaders + Sector Rotation
"""
import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

PIPELINE = [
    ("1. Download latest bhavcopy",                "update_nse_bhavcopy.py"),
    ("2. Update NSE stock database",               "update_nse_database.py"),
    ("3. Update volume from bhavcopy",             "update_nse_with_volume_final.py"),
    ("4. Build D/W/M/Q timeframes",                "build_timeframes_fixed.py"),
    ("5. Calculate StochRSI all TF",               "calculate_stochrsi_all_timeframes.py"),
    ("6. Calculate MACD all TF",                   "calculate_macd_all_timeframes.py"),
    ("7. Calculate SuperTrend all TF",             "calculate_supertrend_all_timeframes.py"),
    ("8. Calculate Elliott Trendline all TF",      "elliott_trendline_all_timeframes.py"),
    ("9. Add main industry mapping",               "add_main_industry_all_timeframes.py"),
    ("10. Map ISIN using company name",            "map_isin_company_only.py"),
    ("11. Generate industry phase history",        "generate_industry_phase_history.py"),
    ("12. Generate historical leaders",            "generate_historical_leaders_final.py"),
    ("13. Industry leaders engine",                "industry_leaders_engine.py"),
    ("14. Industry sector cycle engine",           "industry_sector_cycle_engine.py"),
    ("15. Industry sector volume cycles",          "industry_sector_volume_cycles.py"),
    ("16. Industry cycle signal engine",           "industry_cycle_signal_engine.py"),
    ("17. Industry cycle prediction",              "industry_cycle_prediction_by_industry.py"),
    ("18. Cycle momentum stock selector",          "cycle_momentum_stock_selector.py"),
    ("19. Main industry dashboard (final)",        "main_industry_cycle_dashboard_final.py"),
    ("20. Main industry leaders (final)",          "main_industry_leaders_final.py"),
    ("21. Next industry with leaders",             "next_industry_with_leaders.py"),
    ("22. Next industry phase with leaders",       "next_industry_phase_with_leaders.py"),
    ("23. Top 3 leaders with phase",               "top3_leaders_with_phase.py"),
    ("24. Attach main industry to stocks",         "attach_main_industry_to_stocks.py"),
    ("25. Master dashboard pro",                   "master_dashboard_pro.py"),
    ("26. Master trading dashboard",               "master_trading_dashboard.py"),
    ("27. StochRSI multi-TF reversal rank",        "stochrsi_multi_tf_reversal_rank.py"),
    ("28. StochRSI MTF stage dashboard",           "stochrsi_mtf_stage_dashboard.py"),
    ("29. StochRSI strict hierarchy",              "stochrsi_strict_hierarchy_clean.py"),
    ("30. Scan 1M+W StochRSI",                    "scan_1M_W_stochrsi.py"),
    ("31. Scan M+W+D StochRSI",                   "scan_M_W_D_stochrsi.py"),
    ("32. StochRSI TV multi-TF dashboard",         "stochrsi_tv_multi_tf_dashboard.py"),
    ("33. Hierarchical open trades today",         "hierarchical_open_trades_today.py"),
    ("34. Hierarchical no momentum exit",          "hierarchical_no_momentum_today_exit.py"),
    ("35. Build Elliott dashboard",                "build_elliott_dashboard.py"),
    ("36. Build MACD dashboard",                   "build_macd_dashboard.py"),
]


def run():
    print("\n" + "=" * 60)
    print("  🚀 PIPELINE 3: BHAVCOPY → INDUSTRY LEADERS + SECTOR ROTATION")
    print("=" * 60)

    for step_name, script in PIPELINE:
        script_path = os.path.join(SCRIPTS_DIR, script)
        print(f"\n▶ {step_name} ({script})")
        result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR)
        if result.returncode != 0:
            print(f"❌ FAILED at step: {step_name}")
            sys.exit(1)
        print(f"✅ {step_name} completed")

    print("\n" + "=" * 60)
    print("  ✅ PIPELINE 3 COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    run()