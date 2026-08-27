# Historical Test Results

Run historical tests for the starter MLB prediction model and view the results
in a dashboard.

## One-Step Run

From this folder:

```powershell
.\run_historical_tests.ps1
```

To include closing-line betting results for seasons covered by the public odds
dataset, download the optional odds file first:

```powershell
.\download_odds_history.ps1
.\run_historical_tests.ps1
```

If `python` is not on your PATH:

```powershell
.\run_historical_tests.ps1 -PythonExe C:\Users\ryant\AppData\Local\Programs\Python\Python312\python.exe
```

## Result Buckets

The run creates separate results for:

```text
2023
2024
2026
2026 through August 20
```

Outputs:

```text
outputs\summary.csv
outputs\dashboard.md
outputs\dashboard.html
outputs\predictions_2023.csv
outputs\predictions_2024.csv
outputs\predictions_2026.csv
outputs\predictions_2026_through_aug20.csv
```

View the GitHub-rendered dashboard table at:

```text
Historical Test Results\outputs\dashboard.md
```

Open the richer local dashboard at:

```text
Historical Test Results\outputs\dashboard.html
```

## Metrics

The dashboard reports:

- games tested
- winner accuracy
- home/away score MAE
- total runs MAE
- margin MAE
- average predicted total
- average actual total
- closing moneyline coverage, win percentage, and ROI
- closing ATS/run-line coverage, win percentage, and ROI
- closing totals coverage, win percentage, and ROI
- feature coverage for odds history, starting pitchers, lineups, bullpen state,
  injuries, and weather

## Data Coverage

Odds history loads from:

```text
data\raw\mlb_odds_dataset.json
```

The supported public odds dataset currently covers 2021-04-01 through
2025-08-16. That means 2023 and 2024 can show closing-line betting results
when the file is present. The 2026 buckets still show model-performance metrics
unless a 2026 odds file is added later.

Starting pitcher, lineup, bullpen, injury, and weather coverage are reported
explicitly. Missing feature coverage is not imputed or backfilled by the
dashboard.
