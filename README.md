# VarianceDesk

VarianceDesk is an offline Windows desktop application for budget-versus-actual analysis. It includes 24 months of deterministic fictional data, local SQLite storage, validated imports, forecasts, and Excel/PDF management reports.

## Windows launch

Download `VarianceDesk-Windows-x64.zip` from the v1.0.0 release or build artifact, extract it, then double-click `VarianceDesk.exe`. No Python, web server, account, or internet connection is required after download.

## Features

- Executive revenue, expense, operating-income, margin, trend, and department views.
- Favorable variance: revenue actuals above budget and expense actuals below budget are positive. Percentages are omitted for zero budgets.
- CSV/XLSX validation, duplicate detection, reusable demo data, and SQLite persistence.
- Transparent 12-month base, optimistic, and pessimistic forecasts based on growth assumptions.
- Excel and PDF reports that reconcile with application totals and deterministic commentary based only on the data.

## Development

```bash
python -m pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen pytest
python -m variancedesk --self-test --headless
python -m variancedesk
```

GitHub Actions runs tests on Linux and Windows, creates the one-folder PyInstaller bundle, runs `VarianceDesk.exe --self-test --headless`, and uploads the verified ZIP. A version tag publishes that same ZIP as a release asset.

## Architecture

`finance` holds calculations and scenarios; `imports` validates external data; `storage` owns SQLite; `reporting` exports documents; and `ui` composes the Qt desktop experience. Financial calculations remain outside the UI for direct verification.

## Fictional case study

The demo data contains seasonal revenue growth and departmental variance patterns. The dashboard identifies material contributors so management can investigate volume, pricing, staffing, and vendor questions. Commentary identifies numbers needing attention without claiming causes the data cannot establish.

## Verification

Tests cover formulas, imports, persistence, forecasts, reports, the UI dashboard, application startup, and the deterministic package diagnostic.
