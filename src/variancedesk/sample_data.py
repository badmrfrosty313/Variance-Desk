"""Deterministic fictional data used for demonstrations and self-tests."""
from __future__ import annotations

from datetime import date


DEPARTMENTS = ("Sales", "Operations", "Product", "G&A")


def demo_transactions() -> list[dict]:
    """Return 24 months of fictional, reproducible budget-versus-actual records."""
    result = []
    for index in range(24):
        year, month = 2024 + index // 12, index % 12 + 1
        period = date(year, month, 1).isoformat()[:7]
        revenue_budget = 180_000 + index * 4_000
        revenue_actual = revenue_budget * (1 + ((index % 5) - 2) / 100)
        expense_budget = 115_000 + index * 2_300
        expense_actual = expense_budget * (1 + ((index % 4) - 1.5) / 100)
        result.extend([
            {"period": period, "department": "Sales", "account": "Subscription Revenue", "kind": "revenue", "budget": round(revenue_budget, 2), "actual": round(revenue_actual, 2)},
            {"period": period, "department": "Operations", "account": "Operating Expenses", "kind": "expense", "budget": round(expense_budget, 2), "actual": round(expense_actual, 2)},
        ])
    return result


def monthly_history() -> list[dict]:
    rows = demo_transactions()
    output = []
    for period in sorted({row["period"] for row in rows}):
        period_rows = [row for row in rows if row["period"] == period]
        output.append({"period": period,
                       "actual_revenue": next(row["actual"] for row in period_rows if row["kind"] == "revenue"),
                       "actual_expenses": next(row["actual"] for row in period_rows if row["kind"] == "expense")})
    return output
