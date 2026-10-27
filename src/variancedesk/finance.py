"""Transparent financial calculations used by the dashboard and reports.

Positive variance is favourable: actual above budget for revenue and actual
below budget for expense.  Percentage variance is omitted when budget is zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class Scenario(StrEnum):
    BASE = "Base"
    OPTIMISTIC = "Optimistic"
    PESSIMISTIC = "Pessimistic"


@dataclass(frozen=True)
class ForecastAssumptions:
    revenue_growth: float = 0.03
    expense_growth: float = 0.02
    optimistic_adjustment: float = 0.03
    pessimistic_adjustment: float = -0.03


def variance(actual: float, budget: float, kind: str) -> tuple[float, float | None]:
    """Return favourable dollar and percent variance for an account kind."""
    direction = 1 if kind.lower() in {"revenue", "income"} else -1
    amount = (actual - budget) * direction
    return round(amount, 2), (round(amount / abs(budget) * 100, 2) if budget else None)


def variance_analysis(rows: Iterable[dict]) -> list[dict]:
    """Add variance fields to period/account records without mutating inputs."""
    result = []
    for row in rows:
        item = dict(row)
        amount, percent = variance(float(item["actual"]), float(item["budget"]), item["kind"])
        item.update(variance=amount, variance_percent=percent, favorable=amount >= 0)
        result.append(item)
    return result


def totals(rows: Iterable[dict]) -> dict[str, float]:
    """Aggregate raw budget/actual records into executive financial metrics."""
    values = {"budget_revenue": 0.0, "actual_revenue": 0.0, "budget_expenses": 0.0, "actual_expenses": 0.0}
    for row in rows:
        prefix = "revenue" if row["kind"].lower() in {"revenue", "income"} else "expenses"
        values[f"budget_{prefix}"] += float(row["budget"])
        values[f"actual_{prefix}"] += float(row["actual"])
    values["budget_income"] = values["budget_revenue"] - values["budget_expenses"]
    values["actual_income"] = values["actual_revenue"] - values["actual_expenses"]
    values["operating_margin"] = (values["actual_income"] / values["actual_revenue"] * 100) if values["actual_revenue"] else 0.0
    return {key: round(value, 2) for key, value in values.items()}


def build_forecast(history: Iterable[dict], assumptions: ForecastAssumptions, months: int = 12) -> list[dict]:
    """Create rolling forecast from the most recent actual month by scenario."""
    history = list(history)
    if not history or months < 1:
        return []
    latest = sorted(history, key=lambda row: row["period"])[-1]
    start_year, start_month = map(int, latest["period"].split("-"))
    output = []
    for scenario in Scenario:
        adjustment = 0.0
        if scenario is Scenario.OPTIMISTIC:
            adjustment = assumptions.optimistic_adjustment
        elif scenario is Scenario.PESSIMISTIC:
            adjustment = assumptions.pessimistic_adjustment
        revenue, expenses = float(latest["actual_revenue"]), float(latest["actual_expenses"])
        for offset in range(1, months + 1):
            month_index = start_month + offset
            year = start_year + (month_index - 1) // 12
            month = (month_index - 1) % 12 + 1
            revenue *= 1 + assumptions.revenue_growth + adjustment
            expenses *= 1 + assumptions.expense_growth - adjustment / 2
            output.append({"period": f"{year:04d}-{month:02d}", "scenario": scenario.value,
                           "revenue": round(revenue, 2), "expenses": round(expenses, 2),
                           "operating_income": round(revenue - expenses, 2)})
    return output
