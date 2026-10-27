"""Application entry point and deterministic packaged diagnostic."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def self_test() -> int:
    """Exercise packaged resources without changing normal application data."""
    try:
        from .sample_data import demo_transactions
        from .finance import totals
        from .reporting import export_excel, export_pdf

        records = demo_transactions()
        summary = totals(records)
        if not records or summary["actual_revenue"] <= 0:
            raise RuntimeError("Demo financial data did not reconcile")
        with tempfile.TemporaryDirectory(prefix="variancedesk-self-test-") as temp:
            directory = Path(temp)
            excel = export_excel(records, directory / "self-test.xlsx")
            pdf = export_pdf(records, directory / "self-test.pdf")
            if not excel.exists() or excel.stat().st_size == 0:
                raise RuntimeError("Excel export verification failed")
            if not pdf.exists() or pdf.stat().st_size == 0:
                raise RuntimeError("PDF export verification failed")
        return 0
    except Exception as error:
        print(f"VarianceDesk self-test failed: {error}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="VarianceDesk")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    from PySide6.QtWidgets import QApplication
    from .ui import DashboardWindow
    from .sample_data import demo_transactions
    app = QApplication(sys.argv)
    window = DashboardWindow(demo_transactions())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
