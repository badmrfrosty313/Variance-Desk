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
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


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
    def __init__(self, records: Iterable[Any] = (), parent: QWidget | None = None):
        super().__init__(parent)
        self._records = list(records)
        self.setWindowTitle("VarianceDesk — FP&A Dashboard")
        self.resize(1180, 760)
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root); layout.setContentsMargins(24, 20, 24, 24); layout.setSpacing(16)
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
        layout.addLayout(heading)
        cards = QGridLayout(); cards.setHorizontalSpacing(12)
        self.cards = {name: MetricCard(title) for name, title in [
            ("revenue", "Revenue"), ("expenses", "Expenses"),
            ("income", "Operating income"), ("margin", "Operating margin"),
        ]}
        for col, card in enumerate(self.cards.values()): cards.addWidget(card, 0, col)
        layout.addLayout(cards)
        self.chart = TrendChart(); layout.addWidget(self.chart)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Department", "Account", "Budget", "Actual", "Variance", "Variance %"])
        self.table.setAlternatingRowColors(True); self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        self.setStyleSheet("""
          QMainWindow { background: #101827; color: #f4f7fb; }
          QLabel { color: #dce6f5; } #appTitle { font-size: 26px; font-weight: 700; }
          #subtitle, #metricTitle { color: #93a4bd; } #metricTitle { font-size: 10px; font-weight: 700; }
          #metricCard { background: #172033; border: 1px solid #293752; border-radius: 8px; }
          #metricValue { font-size: 22px; font-weight: 700; } QComboBox, QTableWidget { background: #172033; color: #eaf0fa; border: 1px solid #35445e; padding: 5px; }
          QHeaderView::section { background: #202c43; color: #dce6f5; border: 0; padding: 6px; }
        """)

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
        for r in records:
            group = groups[str(_get(r, "period", "Unknown"))]; group[0] += float(_get(r, "budget", 0)); group[1] += float(_get(r, "actual", 0))
        self.chart.set_points((key, values[0], values[1]) for key, values in sorted(groups.items()))
        self.table.setSortingEnabled(False); self.table.setRowCount(len(records))
        for row, r in enumerate(records):
            b, a = float(_get(r, "budget", 0)), float(_get(r, "actual", 0)); variance = a - b
            values = [str(_get(r, "department", "")), str(_get(r, "account", "")), _money(b), _money(a), _money(variance), "—" if not b else f"{variance / abs(b):.1%}"]
            for col, value in enumerate(values): self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.setSortingEnabled(True)


def launch(records: Iterable[Any] = ()) -> int:
    app = QApplication.instance() or QApplication([])
    window = DashboardWindow(records); window.show()
    return app.exec()

