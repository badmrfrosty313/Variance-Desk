"""Validated, offline imports for VarianceDesk financial facts."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = ("period", "department", "account", "kind", "budget", "actual")
VALID_KINDS = {"revenue", "expense"}


@dataclass(frozen=True)
class FinancialFact:
    period: str
    department: str
    account: str
    kind: str
    budget: float
    actual: float

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.period, self.department, self.account, self.kind)


@dataclass
class ImportResult:
    records: list[FinancialFact] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duplicate_count: int = 0

    @property
    def valid(self) -> bool:
        return bool(self.records) and not self.errors


def _validate_row(row: dict[str, object], line: int) -> FinancialFact:
    missing = [column for column in REQUIRED_COLUMNS if not str(row.get(column, "")).strip()]
    if missing:
        raise ValueError(f"Row {line}: missing required values: {', '.join(missing)}")
    period = str(row["period"]).strip()
    try:
        datetime.strptime(period, "%Y-%m")
    except ValueError as exc:
        raise ValueError(f"Row {line}: period must be YYYY-MM") from exc
    kind = str(row["kind"]).strip().lower()
    if kind not in VALID_KINDS:
        raise ValueError(f"Row {line}: kind must be revenue or expense")
    try:
        budget, actual = float(row["budget"]), float(row["actual"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {line}: budget and actual must be numeric") from exc
    return FinancialFact(period, str(row["department"]).strip(), str(row["account"]).strip(), kind, budget, actual)


def validate_rows(rows: Iterable[dict[str, object]]) -> ImportResult:
    result = ImportResult()
    seen: set[tuple[str, str, str, str]] = set()
    for line, row in enumerate(rows, start=2):
        try:
            record = _validate_row(row, line)
        except ValueError as exc:
            result.errors.append(str(exc))
            continue
        if record.key in seen:
            result.duplicate_count += 1
            result.errors.append(f"Row {line}: duplicate record for {' / '.join(record.key)}")
            continue
        seen.add(record.key)
        result.records.append(record)
    return result


def import_file(path: str | Path) -> ImportResult:
    """Read a CSV or XLSX template and return valid records plus actionable errors."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        with source.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or set(REQUIRED_COLUMNS) - set(reader.fieldnames):
                return ImportResult(errors=["Template must contain columns: " + ", ".join(REQUIRED_COLUMNS)])
            return validate_rows(reader)
    if suffix == ".xlsx":
        try:
            import openpyxl
        except ImportError:
            return ImportResult(errors=["Excel import requires openpyxl."])
        sheet = openpyxl.load_workbook(source, read_only=True, data_only=True).active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return ImportResult(errors=["Workbook is empty."])
        headers = [str(value).strip() if value is not None else "" for value in values[0]]
        if set(REQUIRED_COLUMNS) - set(headers):
            return ImportResult(errors=["Template must contain columns: " + ", ".join(REQUIRED_COLUMNS)])
        return validate_rows(dict(zip(headers, row)) for row in values[1:])
    return ImportResult(errors=["Choose a CSV or XLSX file."])
