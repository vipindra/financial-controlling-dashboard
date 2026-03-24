"""
Sample data generator for the Financial Controlling Dashboard.

Generates a realistic full fiscal year for a mid-sized engineering
or technology company with five cost centres:

    CC-101  Research and Development
    CC-102  Sales and Business Development
    CC-103  Operations and Logistics
    CC-104  Finance and Administration
    CC-105  IT and Infrastructure

Data characteristics:
    - Some cost centres run over budget (realistic, not perfect)
    - Seasonal spending patterns (Q4 higher in some categories)
    - Forecast accuracy degrades slightly in later months (also realistic)
    - Mix of recurring and one-off transactions
"""

import random
from datetime import date, timedelta
from src.database import (
    initialise, insert_cost_centre, insert_budget,
    insert_actual, insert_forecast
)

random.seed(2025)

FISCAL_YEAR = 2025

COST_CENTRES = [
    ("CC-101", "Research and Development",      "Dr. Priya Sharma",   "APAC"),
    ("CC-102", "Sales and Business Development","Rahul Mehta",        "APAC"),
    ("CC-103", "Operations and Logistics",      "Sunita Patel",       "APAC"),
    ("CC-104", "Finance and Administration",    "Vikram Iyer",        "APAC"),
    ("CC-105", "IT and Infrastructure",         "Ananya Singh",       "APAC"),
]

CATEGORIES = [
    "Personnel Costs",
    "Travel and Accommodation",
    "Software and Licenses",
    "Equipment and Materials",
    "External Services",
    "Training and Development",
    "Marketing and Events",
]

# Annual budgets per cost centre per category (in INR lakhs)
BUDGETS = {
    "CC-101": {
        "Personnel Costs":         85.00,
        "Travel and Accommodation":12.00,
        "Software and Licenses":    8.50,
        "Equipment and Materials":  6.00,
        "External Services":       14.00,
        "Training and Development": 4.50,
        "Marketing and Events":     2.00,
    },
    "CC-102": {
        "Personnel Costs":         60.00,
        "Travel and Accommodation":22.00,
        "Software and Licenses":    5.00,
        "Equipment and Materials":  2.00,
        "External Services":        8.00,
        "Training and Development": 3.00,
        "Marketing and Events":    18.00,
    },
    "CC-103": {
        "Personnel Costs":         45.00,
        "Travel and Accommodation": 8.00,
        "Software and Licenses":    3.00,
        "Equipment and Materials": 20.00,
        "External Services":       12.00,
        "Training and Development": 2.00,
        "Marketing and Events":     1.00,
    },
    "CC-104": {
        "Personnel Costs":         35.00,
        "Travel and Accommodation": 5.00,
        "Software and Licenses":    6.00,
        "Equipment and Materials":  2.00,
        "External Services":        7.00,
        "Training and Development": 3.50,
        "Marketing and Events":     0.50,
    },
    "CC-105": {
        "Personnel Costs":         40.00,
        "Travel and Accommodation": 4.00,
        "Software and Licenses":   28.00,
        "Equipment and Materials": 15.00,
        "External Services":       10.00,
        "Training and Development": 5.00,
        "Marketing and Events":     0.50,
    },
}

# Spending patterns: some CCs run over (realistic)
# Values are multiplier on monthly budget share
SPEND_PATTERNS = {
    "CC-101": 1.05,   # slight overspend — R&D often does
    "CC-102": 0.95,   # sales slightly under in a tough year
    "CC-103": 1.12,   # operations over — equipment costs rose
    "CC-104": 0.92,   # finance under — cost-conscious team
    "CC-105": 1.08,   # IT over — unexpected software renewals
}

# Seasonal multiplier by month (Q4 heavier spending is common)
SEASONAL = {
    1: 0.75, 2: 0.80, 3: 0.90,
    4: 0.95, 5: 1.00, 6: 1.05,
    7: 0.95, 8: 0.95, 9: 1.05,
    10: 1.10, 11: 1.15, 12: 1.30
}

DESCRIPTIONS = {
    "Personnel Costs":          ["Monthly salaries", "Contract staff", "Overtime payments", "Bonus payments"],
    "Travel and Accommodation": ["Client visit travel", "Conference travel", "Team offsite accommodation", "Flight bookings"],
    "Software and Licenses":    ["Annual license renewal", "SaaS subscription", "Tool upgrade", "Developer tools"],
    "Equipment and Materials":  ["Lab equipment purchase", "Office supplies", "Hardware procurement", "Safety equipment"],
    "External Services":        ["Consulting fees", "Legal review", "Audit services", "Outsourced work"],
    "Training and Development": ["Online course batch", "Certification program", "Workshop fees", "Training platform"],
    "Marketing and Events":     ["Campaign spend", "Trade show booth", "Promotional materials", "Client event"],
}


def generate(db_path: str, verbose: bool = True) -> None:
    initialise(db_path)

    if verbose:
        print(f"Generating sample data for fiscal year {FISCAL_YEAR}...")

    cc_ids = {}
    for code, name, owner, region in COST_CENTRES:
        cc_id = insert_cost_centre(code, name, owner, region, db_path)
        cc_ids[code] = cc_id

    # Insert budgets
    for code, categories in BUDGETS.items():
        for category, amount in categories.items():
            insert_budget(cc_ids[code], FISCAL_YEAR, category, amount, db_path)

    # Generate monthly actuals and forecasts
    total_transactions = 0
    for month in range(1, 13):
        month_start = date(FISCAL_YEAR, month, 1)
        days_in_month = (
            date(FISCAL_YEAR, month + 1, 1) - month_start
        ).days if month < 12 else 31

        for code, categories in BUDGETS.items():
            cc_id = cc_ids[code]
            pattern = SPEND_PATTERNS[code]
            seasonal = SEASONAL[month]

            for category, annual_budget in categories.items():
                # Monthly budget share with variance
                monthly_base = (annual_budget / 12) * pattern * seasonal
                noise = random.uniform(0.88, 1.14)
                monthly_spend = monthly_base * noise

                # Split into 2-4 transactions per category per month
                num_tx = random.randint(1, 4) if category != "Personnel Costs" else 1
                amounts = []
                remaining = monthly_spend
                for i in range(num_tx - 1):
                    tx = remaining * random.uniform(0.2, 0.6)
                    amounts.append(round(tx, 2))
                    remaining -= tx
                amounts.append(round(remaining, 2))

                for amount in amounts:
                    post_day = random.randint(1, days_in_month)
                    post_date = date(FISCAL_YEAR, month, post_day)
                    desc = random.choice(DESCRIPTIONS[category])
                    insert_actual(cc_id, post_date, category,
                                  round(amount, 2), desc, db_path)
                    total_transactions += 1

                # Forecast: slightly off actuals (forecasts are never perfect)
                # Forecast accuracy degrades a little later in the year
                accuracy_noise = random.uniform(0.90, 1.12) if month <= 6 else random.uniform(0.85, 1.18)
                forecast_amount = round(monthly_spend * accuracy_noise, 2)
                insert_forecast(cc_id, FISCAL_YEAR, month,
                                category, forecast_amount, db_path)

    if verbose:
        print(f"  Cost centres:   {len(COST_CENTRES)}")
        print(f"  Budget lines:   {sum(len(v) for v in BUDGETS.values())}")
        print(f"  Transactions:   {total_transactions}")
        print(f"  Months covered: 12 (Jan to Dec {FISCAL_YEAR})")
        print("Sample data ready.\n")
