#!/usr/bin/env python3
"""
Financial Controlling Dashboard — CLI entry point.

Usage:
    python main.py                     Run full pipeline with sample data
    python main.py --year 2025         Specify fiscal year
    python main.py --reset             Wipe database and regenerate sample data
    python main.py --report-only       Skip data generation, just run report
    python main.py --summary           Print terminal summary only, no Excel

This tool models a real financial controlling cycle:
    1. Load expense data into a structured SQLite database
    2. Run variance analysis against approved budgets
    3. Score cost centre health and flag breaches
    4. Analyse rolling forecast accuracy
    5. Generate a formatted Excel management report
"""

import argparse
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "controlling.db")
FISCAL_YEAR = 2025


def print_terminal_summary(fiscal_year: int, db_path: str) -> None:
    from src.analysis import (
        build_executive_summary,
        analyse_variance_flags,
        analyse_cost_centre_health,
    )

    summary = build_executive_summary(fiscal_year, db_path)
    flags   = analyse_variance_flags(fiscal_year, db_path)
    health  = analyse_cost_centre_health(fiscal_year, db_path)

    W = 60
    print(f"\n  {'=' * W}")
    print(f"  {'FINANCIAL CONTROLLING DASHBOARD':^{W}}")
    print(f"  {'Fiscal Year ' + str(fiscal_year):^{W}}")
    print(f"  {'=' * W}")

    print(f"\n  EXECUTIVE SUMMARY")
    print(f"  {'-' * W}")
    print(f"  {'Total Annual Budget':<35} INR {summary.total_annual_budget:>10,.2f}L")
    print(f"  {'YTD Actuals':<35} INR {summary.total_ytd_actuals:>10,.2f}L")
    print(f"  {'YTD Variance':<35} INR {summary.total_ytd_variance:>+10,.2f}L  ({summary.total_ytd_variance_pct:+.1f}%)")
    print(f"  {'Avg Forecast Accuracy':<35} {summary.avg_forecast_accuracy_pct:.1f}%")
    print(f"  {'Cost Centres Over Budget':<35} {summary.cost_centres_over_budget}")
    print(f"  {'Critical Alerts':<35} {summary.categories_critical}")
    print(f"  {'Warning Alerts':<35} {summary.categories_warning}")

    print(f"\n  COST CENTRE HEALTH")
    print(f"  {'-' * W}")
    print(f"  {'Cost Centre':<32} {'Grade':>6}  {'Variance':>10}")
    for h in health:
        bar = "▓" * int(abs(h.variance_pct) / 2)
        sign = "+" if h.variance_pct > 0 else ""
        print(f"  {h.name:<32} [{h.health_grade:^5}]  {sign}{h.variance_pct:.1f}%  {bar}")

    if flags:
        print(f"\n  ALERTS")
        print(f"  {'-' * W}")
        for f in flags[:8]:
            icon = "🔴" if f.severity == "Critical" else "🟡" if f.severity == "Warning" else "⚪"
            print(f"  {icon} {f.severity:<10}  {f.cost_centre[:22]:<22}  {f.category[:20]:<20}  {f.variance_pct:+.1f}%")

    print(f"\n  {'=' * W}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Financial Controlling Dashboard"
    )
    parser.add_argument("--year",        type=int, default=FISCAL_YEAR)
    parser.add_argument("--reset",       action="store_true",
                        help="Clear database and regenerate sample data")
    parser.add_argument("--report-only", action="store_true",
                        help="Skip data generation, run report on existing data")
    parser.add_argument("--summary",     action="store_true",
                        help="Print terminal summary only, skip Excel export")
    args = parser.parse_args()

    # Database setup
    if args.reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Database cleared.")

    if not args.report_only:
        if not os.path.exists(DB_PATH):
            print("No database found. Generating sample data...\n")
            from src.database import initialise
            from src.sample_data import generate
            initialise(DB_PATH)
            generate(DB_PATH, verbose=True)
        else:
            from src.database import initialise
            initialise(DB_PATH)

    if not os.path.exists(DB_PATH):
        print("No database found. Run without --report-only first.")
        sys.exit(1)

    # Terminal summary
    print_terminal_summary(args.year, DB_PATH)

    # Excel report
    if not args.summary:
        from src.excel_report import generate_excel_report
        print("  Generating Excel management report...")
        filepath = generate_excel_report(args.year, DB_PATH)
        print(f"  Report saved: {filepath}\n")


if __name__ == "__main__":
    main()
