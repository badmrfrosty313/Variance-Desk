from __future__ import annotations

from variancedesk.__main__ import main, self_test
from variancedesk.sample_data import demo_transactions
from variancedesk.finance import ForecastAssumptions, build_forecast
from variancedesk.ui import DashboardWindow
from PySide6.QtWidgets import QFileDialog


def test_dashboard_loads_demo_records_and_filters(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("VARIANCEDESK_DATA_DIR", str(tmp_path))
    window = DashboardWindow(demo_transactions())
    qtbot.addWidget(window)
    assert window.table.rowCount() == 48
    assert "$" in window.cards["revenue"].value.text()
    window.department_filter.setCurrentText("Sales")
    assert window.table.rowCount() == 24


def test_application_headless_diagnostic():
    assert self_test() == 0
    assert main(["--self-test", "--headless"]) == 0


def test_gui_import_forecast_exports_and_persistence(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("VARIANCEDESK_DATA_DIR", str(tmp_path))
    source = tmp_path / "financials.csv"
    source.write_text("period,department,account,kind,budget,actual\n2025-01,Sales,Subscriptions,revenue,100,120\n2025-01,Ops,Hosting,expense,50,40\n", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(source), "CSV"))
    window = DashboardWindow()
    qtbot.addWidget(window)
    window.show_page(3)
    window.import_button.click()
    assert window.table.rowCount() == 2
    assert "Imported 2" in window.import_status.text()

    window.show_page(2)
    base = [r["revenue"] for r in window._forecast if r["scenario"] == "Base"]
    base_expenses = [r["expenses"] for r in window._forecast if r["scenario"] == "Base"]
    assert window.revenue_growth.value() == 3
    assert window._assumption_dict()["revenue_growth"] == .03
    window.revenue_growth.setValue(10)
    window.recalculate_forecast_button.click()
    changed = [r["revenue"] for r in window._forecast if r["scenario"] == "Base"]
    assert changed != base
    assert changed[0] == 120 * 1.10
    window.scenario_filter.setCurrentText("Base")
    visible = {window.forecast_table.item(i, 0).text(): window.forecast_table.item(i, 2).text() for i in range(window.forecast_table.rowCount())}
    assert visible[window._forecast[0]["period"]] == f"${changed[0]:,.0f}"
    window.expense_growth.setValue(8)
    window.recalculate_forecast_button.click()
    expenses_changed = [r["expenses"] for r in window._forecast if r["scenario"] == "Base"]
    assert expenses_changed != base_expenses
    assert expenses_changed[0] == 40 * 1.08
    repeated = list(window._forecast)
    window.recalculate_forecast_button.click()
    assert window._forecast == repeated
    window.scenario_filter.setCurrentText("Optimistic")
    assert window.forecast_table.rowCount() == 12
    assert window.forecast_table.item(0, 1).text() == "Optimistic"
    optimistic = window.forecast_table.item(0, 2).text()
    window.scenario_filter.setCurrentText("Pessimistic")
    assert window.forecast_table.item(0, 1).text() == "Pessimistic"
    assert window.forecast_table.item(0, 2).text() != optimistic
    expected = build_forecast(window._monthly_history(window._records), ForecastAssumptions(**window._assumption_dict()))
    first = next(r for r in expected if r["scenario"] == "Base")
    assert first["revenue"] == window._forecast[0]["revenue"]
    assert window._monthly_history(window._records)[-1]["actual_revenue"] == 120

    xlsx, pdf = tmp_path / "gui.xlsx", tmp_path / "gui.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(xlsx), "XLSX"))
    window.show_page(4); window.excel_button.click()
    assert xlsx.exists() and xlsx.stat().st_size > 0
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(pdf), "PDF"))
    window.pdf_button.click()
    assert pdf.exists() and pdf.stat().st_size > 0
    window.close(); window.store.close()

    reopened = DashboardWindow()
    qtbot.addWidget(reopened)
    assert not reopened.demo_mode
    assert reopened.table.rowCount() == 2
    reopened.store.close()
