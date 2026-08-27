# Run Tomorrow's Predictions

This folder is the one-step interface for tomorrow's MLB predictions.

## One-Step Run

From this folder:

```powershell
.\run.ps1
```

If `python` is not on your PATH:

```powershell
.\run.ps1 -PythonExe C:\Users\ryant\AppData\Local\Programs\Python\Python312\python.exe
```

For a specific date:

```powershell
.\run.ps1 -Date 2026-08-28
```

The runner writes:

```text
latest_predictions.md
outputs\YYYY-MM-DD\tomorrow_predictions.csv
outputs\YYYY-MM-DD\daily_edge_bets.csv
outputs\YYYY-MM-DD\tomorrow_predictions.md
outputs\YYYY-MM-DD\run_summary.json
```

## Optional Daily Market Lines

Daily ML, ATS/run-line, and O/U edge bets require market lines. Add a file named:

```text
daily_market_lines.csv
```

Use this schema:

```text
date,away_team,home_team,away_ml,home_ml,away_spread,home_spread,away_spread_odds,home_spread_odds,total,over_odds,under_odds
```

A sample template is included:

```text
daily_market_lines.sample.csv
```

When `daily_market_lines.csv` is present, the runner selects the top 3 positive
edges for each category: ML, ATS/run-line, and O/U. When it is missing, the
GitHub table shows an explicit no-market-lines placeholder.

## Run In GitHub

1. Open the GitHub repo.
2. Go to `Actions`.
3. Select `Run Tomorrow's Predictions`.
4. Click `Run workflow`.
5. Leave `prediction_date` blank for tomorrow UTC, or enter a date like `2026-08-28`.
6. Download the `mlb-tomorrow-predictions` artifact from the completed run.

The completed Actions run also shows the predictions table directly on the run
summary page. Manual GitHub runs update `latest_predictions.md` in this folder,
so the newest table is viewable in the repo without downloading the artifact.

## What It Does

1. Uses tomorrow's UTC date by default.
2. Pulls the MLB schedule from the public MLB Stats API.
3. Applies the local starter rating model in `team_ratings.csv`.
4. Optionally joins daily market lines from `daily_market_lines.csv`.
5. Writes game-level projected scores, totals, margins, win probabilities, and
   top 3 daily edge bets by ML, ATS/run-line, and O/U.

This is a starter interface, not a certified betting execution model. The next
upgrade should add pitcher projections, lineup/injury context, market odds,
calibrated probabilities, and governance tests.
