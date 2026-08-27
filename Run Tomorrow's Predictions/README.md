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
outputs\YYYY-MM-DD\tomorrow_predictions.csv
outputs\YYYY-MM-DD\tomorrow_predictions.md
outputs\YYYY-MM-DD\run_summary.json
```

## What It Does

1. Uses tomorrow's UTC date by default.
2. Pulls the MLB schedule from the public MLB Stats API.
3. Applies the local starter rating model in `team_ratings.csv`.
4. Writes game-level projected scores, totals, margins, and win probabilities.

This is a starter interface, not a certified betting execution model. The next
upgrade should add pitcher projections, lineup/injury context, market odds,
calibrated probabilities, and governance tests.
