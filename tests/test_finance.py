from variancedesk.finance import ForecastAssumptions, build_forecast, totals, variance, variance_analysis
from variancedesk.sample_data import demo_transactions, monthly_history


def test_expense_underspend_is_favorable():
    assert variance(90, 100, "expense") == (10, 10.0)
    assert variance(110, 100, "revenue") == (10, 10.0)


def test_zero_budget_has_no_percentage():
    assert variance(100, 0, "revenue") == (100, None)


def test_demo_data_is_deterministic_and_complete():
    rows = demo_transactions()
    assert len(rows) == 48
    assert rows == demo_transactions()
    assert len(monthly_history()) == 24


def test_variance_and_executive_totals_reconcile():
    rows = demo_transactions()[:2]
    analyzed = variance_analysis(rows)
    assert analyzed[0]["favorable"] is False
    summary = totals(rows)
    assert summary["actual_income"] == round(summary["actual_revenue"] - summary["actual_expenses"], 2)


def test_forecast_has_all_scenarios_and_periods():
    forecast = build_forecast(monthly_history(), ForecastAssumptions())
    assert len(forecast) == 36
    assert {row["scenario"] for row in forecast} == {"Base", "Optimistic", "Pessimistic"}
    assert forecast[12]["revenue"] > forecast[0]["revenue"]
