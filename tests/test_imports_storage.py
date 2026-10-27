from variancedesk.imports import FinancialFact, validate_rows
from variancedesk.storage import FinancialStore


def test_validation_reports_duplicates_and_bad_period() -> None:
    result = validate_rows([
        {"period": "2025-01", "department": "Sales", "account": "Revenue", "kind": "revenue", "budget": "10", "actual": "12"},
        {"period": "2025-01", "department": "Sales", "account": "Revenue", "kind": "revenue", "budget": "10", "actual": "12"},
        {"period": "January", "department": "Sales", "account": "Revenue", "kind": "revenue", "budget": "10", "actual": "12"},
    ])
    assert len(result.records) == 1
    assert result.duplicate_count == 1
    assert len(result.errors) == 2


def test_sqlite_store_deduplicates_and_resets(tmp_path) -> None:
    fact = FinancialFact("2025-01", "Sales", "Subscriptions", "revenue", 100.0, 120.0)
    with FinancialStore(tmp_path / "facts.db") as store:
        assert store.save([fact, fact]) == 1
        assert store.fetch("Sales") == [fact]
        store.reset()
        assert store.fetch() == []
