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
    parser.add_argument("--smoke-gui", action="store_true")
    parser.add_argument("--qa-e2e", action="store_true")
    parser.add_argument("--qa-output", default="qa-results")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.qa_e2e:
        from .qa import run_packaged_qa
        return run_packaged_qa(args.qa_output)
    from PySide6.QtWidgets import QApplication
    from .ui import DashboardWindow
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        window = DashboardWindow()
        window.show()
        if args.smoke_gui:
            app.processEvents()
            if not window.isVisible() or window.table.rowCount() == 0:
                raise RuntimeError("Dashboard did not render the demonstration records")
            window.close()
            app.processEvents()
            return 0
    except Exception as error:
        print(f"VarianceDesk GUI startup failed: {error}", file=sys.stderr)
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
