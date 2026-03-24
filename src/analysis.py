"""
Variance analysis and financial controlling engine.

This module takes raw query results from the database layer and
produces structured analytical outputs:

    - YTD variance summary with risk flags
    - Forecast accuracy scoring per cost centre
    - Month-on-month spend trend analysis
    - Cost centre health ratings
    - Executive summary metrics

These are the outputs that go into the monthly management report.
"""

from dataclasses import dataclass, field
from typing import Optional
from src.database import (
    get_ytd_variance,
    get_monthly_trend,
    get_category_breakdown,
    get_monthly_actuals_by_cc,
    get_top_transactions,
)


@dataclass
class VarianceFlag:
    """A single cost centre or category that has breached a threshold."""
    cost_centre: str
    owner: str
    category: str
    annual_budget: float
    ytd_actuals: float
    variance: float
    variance_pct: float
    severity: str          # "Critical", "Warning", "Watch"
    message: str


@dataclass
class CostCentreHealth:
    """Overall health rating for a cost centre across all categories."""
    code: str
    name: str
    owner: str
    total_budget: float
    total_actuals: float
    total_variance: float
    variance_pct: float
    health_grade: str      # A / B / C / D / F
    categories_over: int
    categories_under: int


@dataclass
class ForecastAccuracy:
    """How accurate the rolling forecasts were per month."""
    fiscal_month: int
    actual_spend: float
    forecast_spend: float
    variance: float
    accuracy_pct: float    # 100% = perfect, lower = less accurate


@dataclass
class ExecutiveSummary:
    """Top-level numbers for the first page of the management report."""
    fiscal_year: int
    total_annual_budget: float
    total_ytd_actuals: float
    total_ytd_variance: float
    total_ytd_variance_pct: float
    cost_centres_over_budget: int
    cost_centres_on_track: int
    categories_critical: int
    categories_warning: int
    months_with_data: int
    largest_overspend_cc: str
    largest_underspend_cc: str
    avg_forecast_accuracy_pct: float


# ── Thresholds ────────────────────────────────────────────────────────────────
# These mirror the kind of tolerances a real controlling team would set.
CRITICAL_THRESHOLD = 15.0    # over budget by more than 15% = Critical
WARNING_THRESHOLD  = 7.0     # 7-15% over = Warning
WATCH_THRESHOLD    = 3.0     # 3-7% over = Watch


def analyse_variance_flags(fiscal_year: int,
                             db_path: str) -> list[VarianceFlag]:
    """
    Scan all cost centre / category combinations for budget breaches.
    Returns a list of VarianceFlag objects ordered by severity.
    """
    rows = get_ytd_variance(fiscal_year, db_path)
    flags = []

    for r in rows:
        pct = r["variance_pct"] or 0.0
        if pct <= WATCH_THRESHOLD:
            continue

        if pct >= CRITICAL_THRESHOLD:
            severity = "Critical"
            message = (
                f"{r['cost_centre']} has exceeded the {r['category']} budget "
                f"by {pct:.1f}%. Immediate review required."
            )
        elif pct >= WARNING_THRESHOLD:
            severity = "Warning"
            message = (
                f"{r['cost_centre']} is tracking {pct:.1f}% over budget "
                f"in {r['category']}. Monitor closely."
            )
        else:
            severity = "Watch"
            message = (
                f"{r['cost_centre']} is {pct:.1f}% over budget "
                f"in {r['category']}. No action needed yet."
            )

        flags.append(VarianceFlag(
            cost_centre  = r["cost_centre"],
            owner        = r["owner"] or "Unassigned",
            category     = r["category"],
            annual_budget= r["annual_budget"],
            ytd_actuals  = r["ytd_actuals"],
            variance     = r["variance"],
            variance_pct = pct,
            severity     = severity,
            message      = message,
        ))

    severity_order = {"Critical": 0, "Warning": 1, "Watch": 2}
    flags.sort(key=lambda f: (severity_order[f.severity], -f.variance_pct))
    return flags


def analyse_cost_centre_health(fiscal_year: int,
                                 db_path: str) -> list[CostCentreHealth]:
    """
    Roll up all categories per cost centre into a single health grade.

    Grading:
        A  = within 3% of budget in both directions
        B  = 3-7% variance
        C  = 7-15% variance
        D  = 15-25% variance
        F  = over 25% variance
    """
    rows = get_ytd_variance(fiscal_year, db_path)

    cc_map: dict[str, dict] = {}
    for r in rows:
        code = r["code"]
        if code not in cc_map:
            cc_map[code] = {
                "name":           r["cost_centre"],
                "owner":          r["owner"] or "Unassigned",
                "total_budget":   0.0,
                "total_actuals":  0.0,
                "categories_over":  0,
                "categories_under": 0,
            }
        cc_map[code]["total_budget"]  += r["annual_budget"]
        cc_map[code]["total_actuals"] += r["ytd_actuals"]
        if r["variance_pct"] and r["variance_pct"] > 0:
            cc_map[code]["categories_over"] += 1
        elif r["variance_pct"] and r["variance_pct"] < 0:
            cc_map[code]["categories_under"] += 1

    result = []
    for code, data in cc_map.items():
        variance = data["total_actuals"] - data["total_budget"]
        if data["total_budget"] > 0:
            pct = abs(variance / data["total_budget"] * 100)
        else:
            pct = 0.0

        grade = (
            "A" if pct <= 3   else
            "B" if pct <= 7   else
            "C" if pct <= 15  else
            "D" if pct <= 25  else "F"
        )

        result.append(CostCentreHealth(
            code             = code,
            name             = data["name"],
            owner            = data["owner"],
            total_budget     = round(data["total_budget"], 2),
            total_actuals    = round(data["total_actuals"], 2),
            total_variance   = round(variance, 2),
            variance_pct     = round(variance / max(data["total_budget"], 1) * 100, 1),
            health_grade     = grade,
            categories_over  = data["categories_over"],
            categories_under = data["categories_under"],
        ))

    result.sort(key=lambda c: abs(c.variance_pct), reverse=True)
    return result


def analyse_forecast_accuracy(fiscal_year: int,
                                db_path: str) -> list[ForecastAccuracy]:
    """
    Calculate how accurate the rolling forecast was each month.
    100% = forecast matched actuals exactly.
    Below 90% or above 110% is considered poor forecast quality.
    """
    trend = get_monthly_trend(fiscal_year, db_path)
    result = []

    for row in trend:
        actual   = row["actual_spend"]
        forecast = row["forecast_spend"]
        variance = actual - forecast

        if forecast > 0:
            accuracy = max(0.0, 100 - abs(variance / forecast * 100))
        else:
            accuracy = 0.0

        result.append(ForecastAccuracy(
            fiscal_month    = row["fiscal_month"],
            actual_spend    = round(actual, 2),
            forecast_spend  = round(forecast, 2),
            variance        = round(variance, 2),
            accuracy_pct    = round(accuracy, 1),
        ))

    return result


def build_executive_summary(fiscal_year: int, db_path: str) -> ExecutiveSummary:
    """
    Build the top-level summary metrics for the management report cover page.
    """
    variance_rows = get_ytd_variance(fiscal_year, db_path)
    health        = analyse_cost_centre_health(fiscal_year, db_path)
    flags         = analyse_variance_flags(fiscal_year, db_path)
    forecast_acc  = analyse_forecast_accuracy(fiscal_year, db_path)

    total_budget   = sum(r["annual_budget"] for r in variance_rows)
    total_actuals  = sum(r["ytd_actuals"]   for r in variance_rows)
    total_variance = total_actuals - total_budget
    total_var_pct  = round(total_variance / max(total_budget, 1) * 100, 1)

    cc_over  = sum(1 for h in health if h.total_variance > 0)
    cc_under = sum(1 for h in health if h.total_variance <= 0)

    critical_count = sum(1 for f in flags if f.severity == "Critical")
    warning_count  = sum(1 for f in flags if f.severity == "Warning")

    months = len(set(r["fiscal_month"] for r in get_monthly_trend(fiscal_year, db_path)))

    over_ccs  = [h for h in health if h.total_variance > 0]
    under_ccs = [h for h in health if h.total_variance < 0]

    largest_over  = max(over_ccs,  key=lambda h: h.total_variance).name  if over_ccs  else "None"
    largest_under = min(under_ccs, key=lambda h: h.total_variance).name  if under_ccs else "None"

    avg_accuracy = (
        sum(f.accuracy_pct for f in forecast_acc) / len(forecast_acc)
        if forecast_acc else 0.0
    )

    return ExecutiveSummary(
        fiscal_year                = fiscal_year,
        total_annual_budget        = round(total_budget, 2),
        total_ytd_actuals          = round(total_actuals, 2),
        total_ytd_variance         = round(total_variance, 2),
        total_ytd_variance_pct     = total_var_pct,
        cost_centres_over_budget   = cc_over,
        cost_centres_on_track      = cc_under,
        categories_critical        = critical_count,
        categories_warning         = warning_count,
        months_with_data           = months,
        largest_overspend_cc       = largest_over,
        largest_underspend_cc      = largest_under,
        avg_forecast_accuracy_pct  = round(avg_accuracy, 1),
    )
