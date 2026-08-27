# Historical Test Results

Run historical tests for the starter MLB prediction model and view the results
in a simple dashboard.

## One-Step Run

From this folder:

```powershell
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

This is a starter baseline model test. It does not include closing odds,
pitchers, lineups, weather, park factors, or governed bet execution yet.
