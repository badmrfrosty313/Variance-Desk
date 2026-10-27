"""Desktop dashboard for VarianceDesk.

The UI is deliberately thin: financial calculations stay in the domain layer and
the window consumes plain records with ``period``, ``department``, ``budget``
and ``actual`` fields.  This keeps it usable for both imported and demo data.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QFormLayout,
)
from .finance import ForecastAssumptions, build_forecast, variance_analysis, totals
from .imports import import_file
from .storage import FinancialStore
from .sample_data import demo_transactions, monthly_history
from .reporting import export_excel, export_pdf
from pathlib import Path
import os


def _get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _money(value: float) -> str:
    return f"${value:,.0f}" if value >= 0 else f"(${abs(value):,.0f})"


@dataclass(frozen=True)
class DashboardSummary:
    revenue: float
    expenses: float
    operating_income: float
    margin: float
    budget: float
    actual: float


class MetricCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.title = QLabel(title.upper())
        self.title.setObjectName("metricTitle")
        self.value = QLabel("—")
        self.value.setObjectName("metricValue")
        layout.addWidget(self.title)
        layout.addWidget(self.value)

    def set_value(self, text: str, favorable: bool | None = None) -> None:
        self.value.setText(text)
        color = "#d7e9df" if favorable is True else "#f6d2d2" if favorable is False else "#f4f7fb"
        self.value.setStyleSheet(f"color: {color};")


class TrendChart(QWidget):
    """Small dependency free budget/actual chart drawn with Qt."""
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(210)
        self._points: list[tuple[str, float, float]] = []

    def set_points(self, points: Iterable[tuple[str, float, float]]) -> None:
        self._points = list(points)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#172033"))
        left, top, right, bottom = 48, 22, 20, 35
        area = self.rect().adjusted(left, top, -right, -bottom)
        if not self._points:
            painter.setPen(QColor("#93a4bd"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data for this selection")
            return
        maximum = max(max(abs(b), abs(a)) for _, b, a in self._points) or 1
        painter.setPen(QPen(QColor("#35445e"), 1))
        for i in range(5):
            y = area.top() + area.height() * i / 4
            painter.drawLine(area.left(), int(y), area.right(), int(y))
        count = len(self._points)
        width = area.width() / max(count, 1)
        bar = max(3, int(width * 0.28))
        for index, (label, budget, actual) in enumerate(self._points):
            x = area.left() + int((index + .5) * width)
            budget_h = int(area.height() * abs(budget) / maximum)
            actual_h = int(area.height() * abs(actual) / maximum)
            painter.fillRect(x - bar - 2, area.bottom() - budget_h, bar, budget_h, QColor("#6c7a96"))
            painter.fillRect(x + 2, area.bottom() - actual_h, bar, actual_h, QColor("#4bc0a8"))
            if index in {0, count - 1} or count <= 6:
                painter.setPen(QColor("#93a4bd"))
                painter.drawText(x - 22, area.bottom() + 20, 44, 14, Qt.AlignmentFlag.AlignCenter, label[-5:])
        painter.setPen(QColor("#eaf0fa"))
        painter.drawText(14, 20, "Budget vs actual")
        painter.setPen(QColor("#6c7a96")); painter.drawText(area.right() - 140, 20, "■ Budget")
        painter.setPen(QColor("#4bc0a8")); painter.drawText(area.right() - 65, 20, "■ Actual")


class DashboardWindow(QMainWindow):
    """Professional, filterable executive dashboard."""
    def __init__(self, records: Iterable[Any] | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = FinancialStore(self.data_path())
        saved_records = self.store.fetch() if records is None else []
        self.demo_mode = records is None and not saved_records
        self._records = list(demo_transactions() if self.demo_mode else saved_records if records is None else records)
        if not self.demo_mode:
            self._records = [self._normalize_record(row) for row in self._records]
        if not self.demo_mode and not self._records:
            self._records = self.store.fetch()
        self.setWindowTitle("VarianceDesk — FP&A Dashboard")
        self.resize(1180, 760)
        self._build()
        self._populate_filters()
        self.refresh()
        self.refresh_forecast()

    @staticmethod
    def data_path() -> Path:
        base = Path(os.environ.get("VARIANCEDESK_DATA_DIR") or (Path(os.environ.get("APPDATA") or Path.home() / ".local" / "share") / "VarianceDesk"))
        base.mkdir(parents=True, exist_ok=True)
        return base / "variancedesk.sqlite3"

    @staticmethod
    def _normalize_record(row: Any) -> dict[str, Any]:
        data = dict(row) if isinstance(row, dict) else vars(row).copy()
        data["kind"] = str(data.get("kind", data.get("category", "expense"))).lower()
        data["category"] = data["kind"]
        return data

    def _build(self) -> None:
        root = QWidget(); self.setCentralWidget(root)
        layout = QHBoxLayout(root); layout.setContentsMargins(0, 0, 0, 0)
        self.navigation = QWidget(); self.navigation.setFixedWidth(190)
        nav = QVBoxLayout(self.navigation); nav.setContentsMargins(16, 20, 12, 20)
        brand = QLabel("VarianceDesk"); brand.setObjectName("appTitle"); nav.addWidget(brand)
        self.nav_buttons = {}
        self.pages = QStackedWidget()
        self.page_names = ["Dashboard", "Variance Analysis", "Forecasting", "Data Management", "Reports"]
        for index, name in enumerate(self.page_names):
            button = QPushButton(name); button.setCheckable(True); button.clicked.connect(lambda checked=False, i=index: self.show_page(i))
            nav.addWidget(button); self.nav_buttons[name] = button
        nav.addStretch()
        self.dataset_label = QLabel(); nav.addWidget(self.dataset_label)
        layout.addWidget(self.navigation)
        body = QWidget(); layout.addWidget(body, 1)
        layout = QVBoxLayout(body); layout.setContentsMargins(20, 16, 20, 18); layout.setSpacing(12)
        heading = QHBoxLayout()
        label = QLabel("VarianceDesk"); label.setObjectName("appTitle")
        subtitle = QLabel("Executive performance dashboard")
        subtitle.setObjectName("subtitle")
        heading.addWidget(label); heading.addWidget(subtitle); heading.addStretch()
        self.period_filter = QComboBox(); self.period_filter.addItem("All periods")
        self.department_filter = QComboBox(); self.department_filter.addItem("All departments")
        self.period_filter.currentTextChanged.connect(self.refresh)
        self.department_filter.currentTextChanged.connect(self.refresh)
        heading.addWidget(QLabel("Period")); heading.addWidget(self.period_filter)
        heading.addWidget(QLabel("Department")); heading.addWidget(self.department_filter)
        self.demo_toggle = QPushButton("Use demo data"); self.demo_toggle.clicked.connect(self.toggle_demo)
        heading.addWidget(self.demo_toggle); layout.addLayout(heading)
        cards = QGridLayout(); cards.setHorizontalSpacing(12)
        self.cards = {name: MetricCard(title) for name, title in [
            ("revenue", "Revenue"), ("expenses", "Expenses"),
            ("income", "Operating income"), ("margin", "Operating margin"),
        ]}
        for col, card in enumerate(self.cards.values()): cards.addWidget(card, 0, col)
        layout.addLayout(cards)
        self.chart = TrendChart(); layout.addWidget(self.chart)
        self.chart_type = QComboBox(); self.chart_type.addItems(["Revenue", "Expenses", "Operating income"])
        self.chart_type.currentTextChanged.connect(self.refresh)
        layout.addWidget(self.chart_type)
        self.table = self._new_table(["Department", "Account", "Budget", "Actual", "Favorable variance", "Variance %"])
        layout.addWidget(self.table, 1)
        dashboard = QWidget(); dash_layout = QVBoxLayout(dashboard)
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): dash_layout.addWidget(item.widget())
            elif item.layout(): dash_layout.addLayout(item.layout())
        self.pages.addWidget(dashboard)
        self._build_analysis_pages()
        body_layout = body.layout()
        body_layout.addWidget(self.pages)
        self.setStyleSheet("""
          QMainWindow { background: #101827; color: #f4f7fb; }
          QLabel { color: #dce6f5; } #appTitle { font-size: 26px; font-weight: 700; }
          #subtitle, #metricTitle { color: #93a4bd; } #metricTitle { font-size: 10px; font-weight: 700; }
          #metricCard { background: #172033; border: 1px solid #293752; border-radius: 8px; }
          #metricValue { font-size: 22px; font-weight: 700; } QComboBox, QTableWidget { background: #172033; color: #eaf0fa; border: 1px solid #35445e; padding: 5px; }
          QHeaderView::section { background: #202c43; color: #dce6f5; border: 0; padding: 6px; }
          QPushButton { background: #202c43; color: #eaf0fa; border: 1px solid #35445e; padding: 8px; text-align: left; }
          QPushButton:checked { background: #276b70; }
        """)

    @staticmethod
    def _new_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True); table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        if len(headers) > 1: header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        for col in range(2, len(headers)): header.setSectionResizeMode(col, header.ResizeMode.ResizeToContents)
        return table

    def _build_analysis_pages(self) -> None:
        self.variance_table = self._new_table(["Period", "Department", "Account", "Kind", "Budget", "Actual", "Favorable variance", "Variance %"])
        page = QWidget(); v = QVBoxLayout(page); v.addWidget(QLabel("Positive values are favorable: revenue above budget and expenses below budget. Percent is blank for zero budgets.")); v.addWidget(self.variance_table); self.pages.addWidget(page)
        forecast_page = QWidget(); f = QVBoxLayout(forecast_page); form = QFormLayout()
        self.revenue_growth = self._spin(.03); self.expense_growth = self._spin(.02)
        self.optimism = self._spin(.03); self.pessimism = self._spin(-.03)
        form.addRow("Base revenue growth", self.revenue_growth); form.addRow("Base expense growth", self.expense_growth); form.addRow("Optimistic adjustment", self.optimism); form.addRow("Pessimistic adjustment", self.pessimism)
        self.recalculate_forecast_button = QPushButton("Recalculate forecast"); self.recalculate_forecast_button.clicked.connect(self.refresh_forecast)
        self.scenario_filter = QComboBox(); self.scenario_filter.addItems(["All scenarios", "Base", "Optimistic", "Pessimistic"]); self.scenario_filter.currentTextChanged.connect(self.refresh_forecast)
        self.forecast_chart = TrendChart(); self.forecast_table = self._new_table(["Period", "Scenario", "Revenue", "Expenses", "Operating income"])
        f.addLayout(form); f.addWidget(self.recalculate_forecast_button); f.addWidget(self.scenario_filter); f.addWidget(self.forecast_chart); f.addWidget(self.forecast_table, 1); self.pages.addWidget(forecast_page)
        data_page = QWidget(); d = QVBoxLayout(data_page); self.import_button = QPushButton("Import CSV or Excel workbook…"); self.import_button.clicked.connect(self.import_dialog)
        self.import_status = QLabel("Imports require period, department, account, kind, budget, actual.")
        d.addWidget(self.import_button); d.addWidget(self.import_status); d.addWidget(QLabel("Imported records are saved locally and retained between launches.")); d.addStretch(); self.pages.addWidget(data_page)
        reports = QWidget(); rp = QVBoxLayout(reports); self.excel_button = QPushButton("Export Excel workbook…"); self.pdf_button = QPushButton("Export PDF report…")
        self.excel_button.clicked.connect(self.export_excel_dialog); self.pdf_button.clicked.connect(self.export_pdf_dialog)
        self.report_status = QLabel("Reports include the currently selected dataset."); rp.addWidget(self.excel_button); rp.addWidget(self.pdf_button); rp.addWidget(self.report_status); rp.addStretch(); self.pages.addWidget(reports)

    @staticmethod
    def _spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(); spin.setRange(-100.0, 200.0); spin.setSingleStep(.25); spin.setDecimals(2); spin.setSuffix(" %"); spin.setValue(value * 100); return spin

    def show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for i, name in enumerate(self.page_names): self.nav_buttons[name].setChecked(i == index)
        if index == 2: self.refresh_forecast()

    def toggle_demo(self) -> None:
        self.demo_mode = not self.demo_mode
        self._records = demo_transactions() if self.demo_mode else self.store.fetch()
        self.demo_toggle.setText("Use imported data" if self.demo_mode else "Use demo data")
        self._populate_filters(); self.refresh()

    def import_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import financial data", "", "Financial files (*.csv *.xlsx)")
        if not path: return
        result = import_file(path)
        if result.records: self.store.save(result.records)
        self.demo_mode = False; self._records = self.store.fetch(); self.demo_toggle.setText("Use demo data"); self._populate_filters(); self.refresh()
        text = f"Imported {len(result.records)} records; saved {len(self._records)} total records."
        if result.errors: text += "\n" + "\n".join(result.errors[:12])
        if result.duplicate_count: text += f"\nDuplicates skipped: {result.duplicate_count}"
        self.import_status.setText(text)

    def export_excel_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel report", "VarianceDesk-Report.xlsx", "Excel workbook (*.xlsx)")
        if path:
            export_excel(self._records, path, self._forecast, self._assumption_dict())
            self.report_status.setText(f"Excel report saved: {path}")

    def export_pdf_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF report", "VarianceDesk-Report.pdf", "PDF report (*.pdf)")
        if path:
            export_pdf(self._records, path)
            self.report_status.setText(f"PDF report saved: {path}")

    def _assumption_dict(self) -> dict[str, float]:
        return {"revenue_growth": self.revenue_growth.value() / 100, "expense_growth": self.expense_growth.value() / 100,
                "optimistic_adjustment": self.optimism.value() / 100, "pessimistic_adjustment": self.pessimism.value() / 100}

    def refresh_forecast(self) -> None:
        history = monthly_history() if self.demo_mode else self._monthly_history(self._records)
        a = self._assumption_dict()
        self._forecast = build_forecast(history, ForecastAssumptions(**a))
        selected = self.scenario_filter.currentText()
        rows = [r for r in self._forecast if selected == "All scenarios" or r["scenario"] == selected]
        self._fill_table(self.forecast_table, rows, ["period", "scenario", "revenue", "expenses", "operating_income"])
        if rows:
            scenario = selected if selected != "All scenarios" else "Base"
            line = [r for r in self._forecast if r["scenario"] == scenario]
            self.forecast_chart.set_points((r["period"], r["revenue"], r["expenses"]) for r in line)

    @staticmethod
    def _monthly_history(rows: list[Any]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"actual_revenue": 0.0, "actual_expenses": 0.0})
        for r in rows:
            kind = _get(r, "kind", _get(r, "category", "expense")); field = "actual_revenue" if kind == "revenue" else "actual_expenses"
            grouped[str(_get(r, "period"))][field] += float(_get(r, "actual", 0))
        return [dict(period=p, **v) for p, v in sorted(grouped.items())]

    @staticmethod
    def _fill_table(table: QTableWidget, rows: list[dict], keys: list[str]) -> None:
        table.setSortingEnabled(False); table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(keys):
                value = row.get(key, "")
                item = QTableWidgetItem(_money(float(value)) if isinstance(value, (int, float)) and key not in ("variance_percent",) else str(value))
                if isinstance(value, (int, float)): item.setData(Qt.ItemDataRole.UserRole, float(value)); item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i, j, item)
        table.setSortingEnabled(True)

    def set_records(self, records: Iterable[Any]) -> None:
        self._records = list(records); self._populate_filters(); self.refresh()

    def _populate_filters(self) -> None:
        periods = sorted({str(_get(r, "period", "")) for r in self._records})
        departments = sorted({str(_get(r, "department", "Unclassified")) for r in self._records})
        self.period_filter.blockSignals(True); self.department_filter.blockSignals(True)
        self.period_filter.clear(); self.period_filter.addItem("All periods"); self.period_filter.addItems(periods)
        self.department_filter.clear(); self.department_filter.addItem("All departments"); self.department_filter.addItems(departments)
        self.period_filter.blockSignals(False); self.department_filter.blockSignals(False)

    def _filtered(self) -> list[Any]:
        period, department = self.period_filter.currentText(), self.department_filter.currentText()
        return [r for r in self._records if (period == "All periods" or str(_get(r, "period")) == period)
                and (department == "All departments" or str(_get(r, "department")) == department)]

    def summary(self, records: Iterable[Any] | None = None) -> DashboardSummary:
        records = self._filtered() if records is None else records
        revenue = expenses = budget = actual = 0.0
        for r in records:
            b, a = float(_get(r, "budget", 0)), float(_get(r, "actual", 0))
            budget += b; actual += a
            if str(_get(r, "category", _get(r, "kind", "expense"))).lower() == "revenue": revenue += a
            else: expenses += a
        income = revenue - expenses
        return DashboardSummary(revenue, expenses, income, income / revenue if revenue else 0.0, budget, actual)

    def refresh(self) -> None:
        if self.period_filter.count() == 1 and self._records: self._populate_filters()
        records = self._filtered(); s = self.summary(records)
        self.cards["revenue"].set_value(_money(s.revenue))
        self.cards["expenses"].set_value(_money(s.expenses))
        self.cards["income"].set_value(_money(s.operating_income), s.operating_income >= 0)
        self.cards["margin"].set_value(f"{s.margin:.1%}", s.margin >= 0)
        groups: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        chart_kind = self.chart_type.currentText().lower() if hasattr(self, "chart_type") else "revenue"
        for r in records:
            kind = str(_get(r, "kind", _get(r, "category", "expense"))).lower()
            if chart_kind == "operating income":
                selected = True
            else:
                selected = kind == ("revenue" if chart_kind == "revenue" else "expense")
            if not selected: continue
            group = groups[str(_get(r, "period", "Unknown"))]
            sign = -1 if chart_kind == "operating income" and kind == "expense" else 1
            group[0] += float(_get(r, "budget", 0)) * sign; group[1] += float(_get(r, "actual", 0)) * sign
        self.chart.set_points((key, values[0], values[1]) for key, values in sorted(groups.items()))
        rows = []
        for r in records:
            row = self._normalize_record(r)
            row["favorable_variance"], row["variance_percent"] = self._variance(row)
            rows.append(row)
        self._fill_table(self.table, rows, ["department", "account", "budget", "actual", "favorable_variance", "variance_percent"])
        self._fill_table(self.variance_table, rows, ["period", "department", "account", "kind", "budget", "actual", "favorable_variance", "variance_percent"])
        self.dataset_label.setText("Demo dataset" if self.demo_mode else f"Imported data · {len(rows)} records")

    @staticmethod
    def _variance(row: dict[str, Any]) -> tuple[float, float | None]:
        result = variance_analysis([{"actual": row["actual"], "budget": row["budget"], "kind": row["kind"]}])[0]
        return result["variance"], result["variance_percent"]


def launch(records: Iterable[Any] = ()) -> int:
    app = QApplication.instance() or QApplication([])
    window = DashboardWindow(records); window.show()
    return app.exec()

