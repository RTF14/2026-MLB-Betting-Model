# 2026 MLB Betting Model

Research and execution workspace for the 2026 MLB betting model.

## Project Layout

```text
src/mlb_betting_model/   Model and execution code
tests/                   Unit and governance tests
scripts/                 CLI scripts and backtest runners
data/raw/                Local raw data, ignored by Git
data/processed/          Local processed data, ignored by Git
notebooks/               Research notebooks
reports/                 Local reports, ignored by Git
governance/              Certification artifacts and release notes
```

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Run tests:

```powershell
pytest
```

## Run Tomorrow's Predictions

Use the local one-step runner:

```powershell
cd "Run Tomorrow's Predictions"
.\run.ps1
```

Outputs are written under:

```text
Run Tomorrow's Predictions\outputs\YYYY-MM-DD\
```

You can also run it directly in GitHub:

1. Open the repo on GitHub.
2. Go to `Actions`.
3. Select `Run Tomorrow's Predictions`.
4. Click `Run workflow`.
5. Leave `prediction_date` blank for tomorrow UTC, or enter a date like `2026-08-28`.
6. Open the completed run to see the predictions table in the run summary.
7. Download the `mlb-tomorrow-predictions` artifact if you want the CSV files.

Manual GitHub runs also update:

```text
Run Tomorrow's Predictions\latest_predictions.md
```

## Historical Test Dashboard

Run the historical tests locally:

```powershell
cd "Historical Test Results"
.\run_historical_tests.ps1
```

Or run it in GitHub:

1. Open the repo on GitHub.
2. Go to `Actions`.
3. Select `Run Historical Tests`.
4. Click `Run workflow`.
5. Open the completed run to see the summary table.
6. Download the `mlb-historical-test-results` artifact for CSVs and dashboard HTML.

GitHub-rendered dashboard:

```text
Historical Test Results\outputs\dashboard.md
```

## Notes

Keep large datasets, generated reports, and local execution outputs out of Git.
Commit source code, tests, templates, docs, and certification artifacts.
