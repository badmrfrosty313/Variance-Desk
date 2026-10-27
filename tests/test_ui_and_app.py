from __future__ import annotations

from variancedesk.__main__ import main, self_test
from variancedesk.sample_data import demo_transactions
from variancedesk.ui import DashboardWindow


def test_dashboard_loads_demo_records_and_filters(qtbot):
    window = DashboardWindow(demo_transactions())
    qtbot.addWidget(window)
    assert window.table.rowCount() == 48
    assert "$" in window.cards["revenue"].value.text()
    window.department_filter.setCurrentText("Sales")
    assert window.table.rowCount() == 24


def test_application_headless_diagnostic():
    assert self_test() == 0
    assert main(["--self-test", "--headless"]) == 0
