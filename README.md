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
6. Open the completed run and download the `mlb-tomorrow-predictions` artifact.

## Notes

Keep large datasets, generated reports, and local execution outputs out of Git.
Commit source code, tests, templates, docs, and certification artifacts.
