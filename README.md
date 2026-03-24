# Financial Controlling Dashboard

A Python and SQL tool that automates the monthly financial controlling cycle — loading expense data, running variance analysis against approved budgets, scoring cost centre health, tracking forecast accuracy, and generating a formatted Excel management report.

Built around the kind of work a finance controlling team does every month: comparing actuals to budget, identifying which cost centres are running over, and producing clear outputs that non-finance stakeholders can read and act on.

---

## What It Does

**Data layer (SQLite)**
Five cost centres, full budget structure by category, 12 months of transaction-level actuals and rolling forecasts. All stored in a local SQLite database — no server, no credentials, runs anywhere.

**Variance engine**
Calculates year-to-date budget vs actuals for every cost centre and expense category. Flags overspends as Critical (over 15%), Warning (7-15%) or Watch (3-7%). Rolls up to a cost centre health grade from A to F.

**Forecast accuracy tracking**
Scores how closely the rolling forecast matched actual spend each month. Surfaces the months where forecast quality was weakest — which is where replanning conversations need to happen.

**Excel management report**
Seven-sheet formatted workbook that mirrors what a real controlling report looks like:

| Sheet | Contents |
|---|---|
| Executive Summary | Top-level KPIs, variance status, key flags |
| Variance Analysis | Full YTD budget vs actuals with traffic light colouring |
| Monthly Trend | Actuals vs forecast month by month |
| Cost Centre Health | Health grades with colour-coded status |
| Top Transactions | Largest individual spend items for spot-check |
| Category Breakdown | Spend distribution across expense categories |
| Forecast Accuracy | Monthly forecast vs actuals with accuracy scoring |

---

## Quickstart

```bash
git clone https://github.com/your-username/financial-controlling-dashboard.git
cd financial-controlling-dashboard

pip install -r requirements.txt

# Run full pipeline — generates sample data and Excel report
python main.py

# Terminal summary only (no Excel file)
python main.py --summary

# Reset and regenerate fresh data
python main.py --reset
```

The Excel report lands in the `/reports` folder.

---

## Sample Output (Terminal)

```
  ============================================================
              FINANCIAL CONTROLLING DASHBOARD
                      Fiscal Year 2025
  ============================================================

  EXECUTIVE SUMMARY
  ------------------------------------------------------------
  Total Annual Budget                    INR   1,486.00L
  YTD Actuals                            INR   1,553.47L
  YTD Variance                           INR     +67.47L  (+4.5%)
  Avg Forecast Accuracy                  91.3%
  Cost Centres Over Budget               3
  Critical Alerts                        2
  Warning Alerts                         4

  COST CENTRE HEALTH
  ------------------------------------------------------------
  Cost Centre                            Grade   Variance
  Operations and Logistics               [ C  ]  +11.8%  ▓▓▓▓▓
  IT and Infrastructure                  [ C  ]  +8.3%   ▓▓▓▓
  Research and Development               [ B  ]  +5.1%   ▓▓
  Sales and Business Development         [ B  ]  -4.2%   ▓▓
  Finance and Administration             [ A  ]  -3.6%   ▓

  ALERTS
  ------------------------------------------------------------
  🔴 Critical    Operations and Logistics    Equipment and Materials  +18.2%
  🔴 Critical    IT and Infrastructure       Software and Licenses    +16.7%
  🟡 Warning     Operations and Logistics    External Services        +12.4%
```

---

## Project Structure

```
financial-controlling-dashboard/
├── main.py                     Entry point and CLI
├── src/
│   ├── database.py             SQLite schema, inserts and query functions
│   ├── sample_data.py          Realistic 12-month data generator
│   ├── analysis.py             Variance engine, health scoring, forecasting
│   ├── excel_report.py         Formatted Excel workbook generator
│   └── __init__.py
├── data/                       SQLite database (gitignored)
├── reports/                    Excel outputs (gitignored)
├── requirements.txt            openpyxl only
└── .gitignore
```

---

## Sample Data Design

The generated dataset is deliberately imperfect — because real financial data never is:

- **Operations and Logistics** runs over budget on Equipment and Materials due to a price increase mid-year
- **IT and Infrastructure** exceeds the Software and Licenses budget from unplanned renewals
- **Finance and Administration** comes in under budget — the tightest-managed cost centre
- Seasonal spending patterns mean Q4 runs heavier in most categories
- Forecast accuracy degrades slightly in later months, which is realistic as plans diverge from reality

This gives the analysis something meaningful to surface rather than a perfectly balanced dataset that produces no flags.

---

## Design Decisions

**Why SQLite and not CSV files?**
The whole point of controlling work is that you can query across dimensions — by cost centre, by category, by month, by year. CSV files force you to reload and filter everything in Python on every run. SQLite lets you express those queries properly in SQL, which is also closer to how this data would live in a real ERP like SAP.

**Why openpyxl and not pandas/matplotlib?**
A finance team receiving this report will open it in Excel, not in a Jupyter notebook. openpyxl produces a workbook that looks like something a finance analyst actually built — with proper formatting, conditional colouring and frozen header rows. The goal is a report someone would forward to their manager, not a script output.

**Why a health grade instead of just a number?**
A percentage variance means something different at different budget sizes. A 12% overspend on a 2L budget is a very different problem from a 12% overspend on a 50L budget. The health grade takes the overall picture into account and gives the reader a single signal they can act on without needing to interpret the numbers themselves.

---

## Extending This

A few natural next steps if you want to take this further:

- Load real data from a CSV export out of SAP, Tally or any ERP by replacing the `sample_data.py` calls with a CSV ingestion function in `src/loader.py`
- Add a rolling 12-month forecast resubmission workflow where each month updates the forecast for the remaining months
- Connect the Excel output to a PowerPoint summary using python-pptx for a fully automated month-end pack

---

## License

MIT. Use it, adapt it, build on it.
