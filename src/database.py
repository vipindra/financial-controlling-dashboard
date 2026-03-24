"""
Database layer for the Financial Controlling Dashboard.

Handles schema creation, data insertion and all aggregation queries.
Uses SQLite so the project runs anywhere with no external database setup.

Tables:
    cost_centres    - Department/team definitions with budget ownership
    budget          - Approved annual budget split by cost centre and category
    actuals         - Monthly actual expenditure transactions
    forecasts       - Rolling forecast entries updated each month
"""

import sqlite3
import os
from datetime import date
from typing import Optional

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "controlling.db")


def get_connection(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialise(db_path: str = DEFAULT_DB) -> None:
    """
    Create all tables if they do not exist.
    Safe to call on every run — uses IF NOT EXISTS throughout.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cost_centres (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            owner       TEXT,
            region      TEXT
        );

        CREATE TABLE IF NOT EXISTS budget (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_centre_id  INTEGER NOT NULL REFERENCES cost_centres(id),
            fiscal_year     INTEGER NOT NULL,
            category        TEXT NOT NULL,
            amount          REAL NOT NULL DEFAULT 0,
            UNIQUE(cost_centre_id, fiscal_year, category)
        );

        CREATE TABLE IF NOT EXISTS actuals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_centre_id  INTEGER NOT NULL REFERENCES cost_centres(id),
            posting_date    DATE NOT NULL,
            fiscal_year     INTEGER NOT NULL,
            fiscal_month    INTEGER NOT NULL,
            category        TEXT NOT NULL,
            description     TEXT,
            amount          REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS forecasts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_centre_id  INTEGER NOT NULL REFERENCES cost_centres(id),
            fiscal_year     INTEGER NOT NULL,
            fiscal_month    INTEGER NOT NULL,
            category        TEXT NOT NULL,
            forecast_amount REAL NOT NULL,
            created_date    DATE NOT NULL,
            UNIQUE(cost_centre_id, fiscal_year, fiscal_month, category)
        );

        CREATE INDEX IF NOT EXISTS idx_actuals_cc   ON actuals(cost_centre_id);
        CREATE INDEX IF NOT EXISTS idx_actuals_date ON actuals(posting_date);
        CREATE INDEX IF NOT EXISTS idx_actuals_ym   ON actuals(fiscal_year, fiscal_month);
        CREATE INDEX IF NOT EXISTS idx_forecast_ym  ON forecasts(fiscal_year, fiscal_month);
    """)
    conn.commit()
    conn.close()


# ── Inserts ──────────────────────────────────────────────────────────────────

def insert_cost_centre(code: str, name: str,
                        owner: Optional[str] = None,
                        region: Optional[str] = None,
                        db_path: str = DEFAULT_DB) -> int:
    conn = get_connection(db_path)
    cur = conn.execute(
        "INSERT OR IGNORE INTO cost_centres (code, name, owner, region) VALUES (?,?,?,?)",
        (code, name, owner, region)
    )
    conn.commit()
    row = conn.execute("SELECT id FROM cost_centres WHERE code=?", (code,)).fetchone()
    conn.close()
    return row["id"]


def insert_budget(cost_centre_id: int, fiscal_year: int,
                   category: str, amount: float,
                   db_path: str = DEFAULT_DB) -> None:
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO budget (cost_centre_id, fiscal_year, category, amount)
           VALUES (?,?,?,?)
           ON CONFLICT(cost_centre_id, fiscal_year, category)
           DO UPDATE SET amount=excluded.amount""",
        (cost_centre_id, fiscal_year, category, amount)
    )
    conn.commit()
    conn.close()


def insert_actual(cost_centre_id: int, posting_date: date,
                   category: str, amount: float,
                   description: Optional[str] = None,
                   db_path: str = DEFAULT_DB) -> None:
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO actuals
               (cost_centre_id, posting_date, fiscal_year, fiscal_month, category, description, amount)
           VALUES (?,?,?,?,?,?,?)""",
        (cost_centre_id, posting_date.isoformat(),
         posting_date.year, posting_date.month,
         category, description, amount)
    )
    conn.commit()
    conn.close()


def insert_forecast(cost_centre_id: int, fiscal_year: int,
                     fiscal_month: int, category: str,
                     forecast_amount: float,
                     db_path: str = DEFAULT_DB) -> None:
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO forecasts
               (cost_centre_id, fiscal_year, fiscal_month, category, forecast_amount, created_date)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(cost_centre_id, fiscal_year, fiscal_month, category)
           DO UPDATE SET forecast_amount=excluded.forecast_amount,
                         created_date=excluded.created_date""",
        (cost_centre_id, fiscal_year, fiscal_month,
         category, forecast_amount, date.today().isoformat())
    )
    conn.commit()
    conn.close()


# ── Queries ───────────────────────────────────────────────────────────────────

def get_ytd_variance(fiscal_year: int, db_path: str = DEFAULT_DB) -> list[dict]:
    """
    Year-to-date variance by cost centre and category.
    Returns budget, actuals YTD, variance amount and variance percent.
    Positive variance = overspend. Negative = underspend.
    """
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            cc.code,
            cc.name          AS cost_centre,
            cc.owner,
            b.category,
            b.amount         AS annual_budget,
            COALESCE(SUM(a.amount), 0)          AS ytd_actuals,
            COALESCE(SUM(a.amount), 0) - b.amount AS variance,
            ROUND(
                (COALESCE(SUM(a.amount), 0) - b.amount)
                / NULLIF(b.amount, 0) * 100, 1
            )                                   AS variance_pct
        FROM budget b
        JOIN cost_centres cc ON cc.id = b.cost_centre_id
        LEFT JOIN actuals a
               ON a.cost_centre_id = b.cost_centre_id
              AND a.fiscal_year    = b.fiscal_year
              AND a.category       = b.category
        WHERE b.fiscal_year = ?
        GROUP BY b.cost_centre_id, b.category
        ORDER BY variance DESC
    """, (fiscal_year,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_trend(fiscal_year: int, db_path: str = DEFAULT_DB) -> list[dict]:
    """
    Month-by-month actuals vs rolling forecast for the full year.
    Used to plot the forecast accuracy trend in the Excel report.
    """
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            a.fiscal_month,
            COALESCE(SUM(a.amount), 0)       AS actual_spend,
            COALESCE(SUM(f.forecast_amount), 0) AS forecast_spend,
            COALESCE(SUM(a.amount), 0)
                - COALESCE(SUM(f.forecast_amount), 0) AS month_variance
        FROM actuals a
        LEFT JOIN forecasts f
               ON f.cost_centre_id = a.cost_centre_id
              AND f.fiscal_year    = a.fiscal_year
              AND f.fiscal_month   = a.fiscal_month
              AND f.category       = a.category
        WHERE a.fiscal_year = ?
        GROUP BY a.fiscal_month
        ORDER BY a.fiscal_month
    """, (fiscal_year,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category_breakdown(fiscal_year: int, db_path: str = DEFAULT_DB) -> list[dict]:
    """Total spend by expense category across all cost centres YTD."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            category,
            SUM(amount)  AS total_spend,
            COUNT(*)     AS transaction_count,
            ROUND(SUM(amount) * 100.0 / SUM(SUM(amount)) OVER (), 1) AS pct_of_total
        FROM actuals
        WHERE fiscal_year = ?
        GROUP BY category
        ORDER BY total_spend DESC
    """, (fiscal_year,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_monthly_actuals_by_cc(fiscal_year: int,
                                db_path: str = DEFAULT_DB) -> list[dict]:
    """Monthly spend per cost centre — used to build the pivot table in Excel."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            cc.code,
            cc.name AS cost_centre,
            a.fiscal_month,
            SUM(a.amount) AS spend
        FROM actuals a
        JOIN cost_centres cc ON cc.id = a.cost_centre_id
        WHERE a.fiscal_year = ?
        GROUP BY a.cost_centre_id, a.fiscal_month
        ORDER BY cc.code, a.fiscal_month
    """, (fiscal_year,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_transactions(fiscal_year: int, top_n: int = 15,
                          db_path: str = DEFAULT_DB) -> list[dict]:
    """Largest individual expense transactions in the year — useful for spot checks."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT
            cc.name AS cost_centre,
            a.posting_date,
            a.category,
            a.description,
            a.amount
        FROM actuals a
        JOIN cost_centres cc ON cc.id = a.cost_centre_id
        WHERE a.fiscal_year = ?
        ORDER BY a.amount DESC
        LIMIT ?
    """, (fiscal_year, top_n)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
