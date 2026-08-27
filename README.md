# 2026 MLB Betting Model

Research and execution workspace for the 2026 MLB betting model.

## Start Here: Run It In GitHub

Use this link:

[Open GitHub Run Page](https://github.com/RTF14/2026-MLB-Betting-Model/actions/workflows/run-tomorrows-predictions.yml)

Then:

1. Click `Run workflow`
2. Click the green `Run workflow` button
3. Wait for the run to finish
4. Click the completed run
5. Read the predictions table on the run page

If you do not see the button, make sure you are signed into GitHub as `RTF14`
and that you are on the repo's `Actions` page.

Latest saved prediction table:

[View Latest Predictions](https://github.com/RTF14/2026-MLB-Betting-Model/blob/main/Run%20Tomorrow%27s%20Predictions/latest_predictions.md)

Historical dashboard:

[View Historical Dashboard](https://github.com/RTF14/2026-MLB-Betting-Model/blob/main/Historical%20Test%20Results/outputs/dashboard.md)

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

1. Open [Run Tomorrow's Predictions](https://github.com/RTF14/2026-MLB-Betting-Model/actions/workflows/run-tomorrows-predictions.yml).
2. Click `Run workflow`.
3. Leave `prediction_date` blank for tomorrow UTC, or enter a date like `2026-08-28`.
4. Click the green `Run workflow` button.
5. Open the completed run to see the predictions table in the run summary.
6. Download the `mlb-tomorrow-predictions` artifact if you want the CSV files.

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

1. Open [Run Historical Tests](https://github.com/RTF14/2026-MLB-Betting-Model/actions/workflows/run-historical-tests.yml).
2. Click `Run workflow`.
3. Leave `include_odds_history` as `true` to calculate closing-line P/L where public odds history is available.
4. Click the green `Run workflow` button.
5. Open the completed run to see the summary and feature-coverage tables.
6. Download the `mlb-historical-test-results` artifact for CSVs and dashboard HTML.

GitHub-rendered dashboard:

```text
Historical Test Results\outputs\dashboard.md
```

The historical dashboard now supports optional odds-history enrichment from:

```text
data\raw\mlb_odds_dataset.json
```

When present, it adds closing moneyline, ATS/run-line, and totals win
percentage/ROI plus the top 3 edge candidates for ML, ATS/run-line, and O/U by
test bucket. Feature coverage for odds history, starting pitchers, lineups,
bullpen state, injuries, and weather is shown separately so missing data is
visible instead of silently assumed.

## Notes

Keep large datasets, generated reports, and local execution outputs out of Git.
Commit source code, tests, templates, docs, and certification artifacts.
