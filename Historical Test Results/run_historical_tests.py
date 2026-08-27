from __future__ import annotations

import csv
import html
import importlib.util
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
PREDICTOR_PATH = REPO_ROOT / "Run Tomorrow's Predictions" / "run_tomorrow_predictions.py"
RATINGS_PATH = REPO_ROOT / "Run Tomorrow's Predictions" / "team_ratings.csv"
OUT = HERE / "outputs"
SCHEDULE_RANGE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&gameTypes=R&startDate={start}&endDate={end}"


def load_predictor():
    spec = importlib.util.spec_from_file_location("tomorrow_predictions", PREDICTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Could not load predictor from {PREDICTOR_PATH}")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fetch_completed_games(start: date, end: date) -> list[dict[str, Any]]:
    url = SCHEDULE_RANGE_URL.format(start=start.isoformat(), end=end.isoformat())
    try:
        with urlopen(url, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Could not fetch MLB schedule/results from {url}: {exc}") from exc

    games: list[dict[str, Any]] = []
    final_states = {"Final", "Game Over", "Completed Early"}
    for slate in payload.get("dates", []):
        game_date = slate.get("date", "")
        for game in slate.get("games", []):
            status = game.get("status", {}).get("detailedState", "")
            if game.get("gameType") != "R":
                continue
            if status not in final_states:
                continue
            teams = game.get("teams", {})
            away = teams.get("away", {})
            home = teams.get("home", {})
            away_team = away.get("team", {}).get("name")
            home_team = home.get("team", {}).get("name")
            if not away_team or not home_team:
                continue
            try:
                away_score = int(away["score"])
                home_score = int(home["score"])
            except (KeyError, TypeError, ValueError):
                continue
            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "game_date": game_date,
                    "game_time_utc": game.get("gameDate", ""),
                    "away_team": away_team,
                    "home_team": home_team,
                    "status": status,
                    "actual_away_runs": away_score,
                    "actual_home_runs": home_score,
                }
            )
    return games


def enrich_prediction(pred: dict[str, Any]) -> dict[str, Any]:
    actual_away = float(pred["actual_away_runs"])
    actual_home = float(pred["actual_home_runs"])
    pred_away = float(pred["pred_away_runs"])
    pred_home = float(pred["pred_home_runs"])
    actual_total = actual_away + actual_home
    pred_total = float(pred["pred_total_runs"])
    actual_margin = actual_home - actual_away
    pred_margin = float(pred["pred_home_margin"])
    actual_winner = pred["home_team"] if actual_home > actual_away else pred["away_team"]
    pred_winner = pred["home_team"] if pred_home >= pred_away else pred["away_team"]
    return {
        **pred,
        "actual_total_runs": actual_total,
        "actual_home_margin": actual_margin,
        "actual_winner": actual_winner,
        "pred_winner": pred_winner,
        "winner_correct": pred_winner == actual_winner,
        "away_score_abs_error": abs(pred_away - actual_away),
        "home_score_abs_error": abs(pred_home - actual_home),
        "total_abs_error": abs(pred_total - actual_total),
        "margin_abs_error": abs(pred_margin - actual_margin),
    }


def mean(values: list[float]) -> float:
    if not values:
        return math.nan
    return sum(values) / len(values)


def summarize(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    games = len(rows)
    winner_accuracy = mean([1.0 if row["winner_correct"] else 0.0 for row in rows])
    return {
        "test": label,
        "games": games,
        "winner_accuracy": round(winner_accuracy, 4) if games else "",
        "away_score_mae": round(mean([float(row["away_score_abs_error"]) for row in rows]), 3) if games else "",
        "home_score_mae": round(mean([float(row["home_score_abs_error"]) for row in rows]), 3) if games else "",
        "total_mae": round(mean([float(row["total_abs_error"]) for row in rows]), 3) if games else "",
        "margin_mae": round(mean([float(row["margin_abs_error"]) for row in rows]), 3) if games else "",
        "avg_pred_total": round(mean([float(row["pred_total_runs"]) for row in rows]), 3) if games else "",
        "avg_actual_total": round(mean([float(row["actual_total_runs"]) for row in rows]), 3) if games else "",
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def md_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return lines


def write_dashboard(summary_rows: list[dict[str, Any]], prediction_sets: dict[str, list[dict[str, Any]]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    columns = [
        "test",
        "games",
        "winner_accuracy",
        "away_score_mae",
        "home_score_mae",
        "total_mae",
        "margin_mae",
        "avg_pred_total",
        "avg_actual_total",
    ]
    lines = [
        "# Historical MLB Starter Model Dashboard",
        "",
        f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        *md_table(summary_rows, columns),
        "",
        "## Notes",
        "",
        "`2026` includes completed regular-season games available at run time. `2026_through_aug20` is locked through August 20, 2026.",
        "",
        "This is a starter baseline model test using public MLB final scores. It is not a betting-grade model yet.",
    ]
    (OUT / "dashboard.md").write_text("\n".join(lines), encoding="utf-8")

    cards = "\n".join(
        f"""
        <section class="card">
          <h2>{html.escape(str(row["test"]))}</h2>
          <div class="metric"><span>Games</span><strong>{row["games"]}</strong></div>
          <div class="metric"><span>Winner Accuracy</span><strong>{float(row["winner_accuracy"]) * 100:.1f}%</strong></div>
          <div class="metric"><span>Total MAE</span><strong>{row["total_mae"]}</strong></div>
          <div class="metric"><span>Margin MAE</span><strong>{row["margin_mae"]}</strong></div>
        </section>
        """
        for row in summary_rows
        if row["games"]
    )
    summary_table = "\n".join(
        [
            "<tr>" + "".join(f"<th>{html.escape(col)}</th>" for col in columns) + "</tr>",
            *[
                "<tr>" + "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in columns) + "</tr>"
                for row in summary_rows
            ],
        ]
    )
    sections = []
    for label, rows in prediction_sets.items():
        preview = rows[:25]
        sections.append(f"<h2>{html.escape(label)}</h2>")
        sections.append("<table>")
        sections.append(
            "<tr><th>Date</th><th>Away</th><th>Home</th><th>Pred</th><th>Actual</th><th>Pred Winner</th><th>Actual Winner</th><th>Total Error</th></tr>"
        )
        for row in preview:
            sections.append(
                "<tr>"
                f"<td>{html.escape(str(row['game_date']))}</td>"
                f"<td>{html.escape(str(row['away_team']))}</td>"
                f"<td>{html.escape(str(row['home_team']))}</td>"
                f"<td>{row['pred_away_runs']}-{row['pred_home_runs']}</td>"
                f"<td>{row['actual_away_runs']}-{row['actual_home_runs']}</td>"
                f"<td>{html.escape(str(row['pred_winner']))}</td>"
                f"<td>{html.escape(str(row['actual_winner']))}</td>"
                f"<td>{float(row['total_abs_error']):.2f}</td>"
                "</tr>"
            )
        sections.append("</table>")

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Historical MLB Starter Model Dashboard</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #172033; background: #f6f7fb; }}
    header {{ padding: 28px 32px; background: #172033; color: white; }}
    main {{ padding: 24px 32px 48px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .card {{ background: white; border: 1px solid #dde3ee; border-radius: 8px; padding: 16px; }}
    .card h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .metric {{ display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid #edf0f5; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin: 12px 0 28px; }}
    th, td {{ padding: 8px 10px; border: 1px solid #dde3ee; text-align: left; font-size: 14px; }}
    th {{ background: #edf2f8; }}
    .note {{ color: #526070; max-width: 900px; }}
  </style>
</head>
<body>
  <header>
    <h1>Historical MLB Starter Model Dashboard</h1>
    <p>Generated at UTC: {html.escape(datetime.now(timezone.utc).isoformat())}</p>
  </header>
  <main>
    <p class="note">Starter baseline test using public MLB final scores. Not betting-grade yet.</p>
    <div class="cards">{cards}</div>
    <h2>Summary</h2>
    <table>{summary_table}</table>
    {''.join(sections)}
  </main>
</body>
</html>
"""
    (OUT / "dashboard.html").write_text(html_doc, encoding="utf-8")


def main() -> int:
    predictor = load_predictor()
    ratings = predictor.load_ratings(RATINGS_PATH)
    tests = {
        "2023": (date(2023, 3, 30), date(2023, 11, 4), "predictions_2023.csv"),
        "2024": (date(2024, 3, 20), date(2024, 10, 30), "predictions_2024.csv"),
        "2026": (date(2026, 3, 1), date(2026, 12, 31), "predictions_2026.csv"),
        "2026_through_aug20": (date(2026, 3, 1), date(2026, 8, 20), "predictions_2026_through_aug20.csv"),
    }
    prediction_sets: dict[str, list[dict[str, Any]]] = {}
    summary_rows: list[dict[str, Any]] = []
    for label, (start, end, filename) in tests.items():
        games = fetch_completed_games(start, end)
        predictions = [enrich_prediction(predictor.predict_game(game, ratings)) for game in games]
        prediction_sets[label] = predictions
        write_csv(predictions, OUT / filename)
        summary_rows.append(summarize(label, predictions))

    write_csv(summary_rows, OUT / "summary.csv")
    write_dashboard(summary_rows, prediction_sets)
    print(json.dumps({"output_dir": str(OUT), "tests": summary_rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
