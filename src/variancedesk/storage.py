"""Local SQLite persistence for imported financial data."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .imports import FinancialFact


class FinancialStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS financial_facts (
                period TEXT NOT NULL, department TEXT NOT NULL, account TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('revenue', 'expense')),
                budget REAL NOT NULL, actual REAL NOT NULL,
                PRIMARY KEY (period, department, account, kind)
            )"""
        )
        self.connection.commit()

    def save(self, facts: Iterable[FinancialFact], replace: bool = False) -> int:
        facts = list(facts)
        clause = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
        cursor = self.connection.executemany(
            f"{clause} INTO financial_facts VALUES (?, ?, ?, ?, ?, ?)",
            [(f.period, f.department, f.account, f.kind, f.budget, f.actual) for f in facts],
        )
        self.connection.commit()
        return cursor.rowcount

    def upsert(self, fact: FinancialFact) -> None:
        self.connection.execute(
            """INSERT INTO financial_facts VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(period, department, account, kind) DO UPDATE SET
               budget=excluded.budget, actual=excluded.actual""",
            (fact.period, fact.department, fact.account, fact.kind, fact.budget, fact.actual),
        )
        self.connection.commit()

    def fetch(self, department: str | None = None) -> list[FinancialFact]:
        query = "SELECT period, department, account, kind, budget, actual FROM financial_facts"
        parameters: tuple[str, ...] = ()
        if department:
            query += " WHERE department = ?"
            parameters = (department,)
        query += " ORDER BY period, department, account"
        return [FinancialFact(**dict(row)) for row in self.connection.execute(query, parameters)]

    def reset(self) -> None:
        self.connection.execute("DELETE FROM financial_facts")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "FinancialStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
