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
SCHEDULE_RANGE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&gameTypes=R&hydrate=probablePitcher,venue&startDate={start}&endDate={end}"
ODDS_PATH = REPO_ROOT / "data" / "raw" / "mlb_odds_dataset.json"
ODDS_SOURCE_URL = "https://github.com/ArnavSaraogi/mlb-odds-scraper/releases/download/dataset/mlb_odds_dataset.json"


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
                    "venue_name": game.get("venue", {}).get("name", ""),
                    "away_probable_pitcher": away.get("probablePitcher", {}).get("fullName", ""),
                    "home_probable_pitcher": home.get("probablePitcher", {}).get("fullName", ""),
                    "status": status,
                    "actual_away_runs": away_score,
                    "actual_home_runs": home_score,
                }
            )
    return games


def normalize_team(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def avg_number(values: list[Any]) -> float | None:
    clean: list[float] = []
    for value in values:
        try:
            if value is not None and value != "":
                clean.append(float(value))
        except (TypeError, ValueError):
            continue
    if not clean:
        return None
    return sum(clean) / len(clean)


def american_to_probability(odds: float) -> float:
    return abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)


def probability_to_american(probability: float) -> float:
    if probability <= 0 or probability >= 1:
        raise ValueError(f"Invalid implied probability: {probability}")
    if probability >= 0.5:
        return -(probability * 100.0) / (1.0 - probability)
    return (100.0 / probability) - 100.0


def avg_american_odds(values: list[Any], max_abs: float) -> float | None:
    probabilities: list[float] = []
    for value in values:
        try:
            odds = float(value)
        except (TypeError, ValueError):
            continue
        if abs(odds) < 100 or abs(odds) > max_abs:
            continue
        probabilities.append(american_to_probability(odds))
    if not probabilities:
        return None
    return probability_to_american(sum(probabilities) / len(probabilities))


def odds_key(game_date: str, away_team: str, home_team: str) -> str:
    return f"{game_date}|{normalize_team(away_team)}|{normalize_team(home_team)}"


def load_odds_index(path: Path = ODDS_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    index: dict[str, dict[str, Any]] = {}
    for game_date, games in payload.items():
        for game in games:
            view = game.get("gameView", {})
            if view.get("gameType") != "R":
                continue
            away = view.get("awayTeam", {}).get("fullName") or view.get("awayTeam", {}).get("displayName", "")
            home = view.get("homeTeam", {}).get("fullName") or view.get("homeTeam", {}).get("displayName", "")
            if not away or not home:
                continue

            odds = game.get("odds", {})
            moneyline = odds.get("moneyline", [])
            spread = odds.get("pointspread", [])
            totals = odds.get("totals", [])
            row = {
                "odds_source": "ArnavSaraogi/mlb-odds-scraper",
                "odds_sportsbooks": ",".join(
                    sorted(
                        {
                            str(book.get("sportsbook"))
                            for market in (moneyline, spread, totals)
                            for book in market
                            if book.get("sportsbook")
                        }
                    )
                ),
                "close_home_ml": avg_american_odds([book.get("currentLine", {}).get("homeOdds") for book in moneyline], 5000),
                "close_away_ml": avg_american_odds([book.get("currentLine", {}).get("awayOdds") for book in moneyline], 5000),
                "open_home_ml": avg_american_odds([book.get("openingLine", {}).get("homeOdds") for book in moneyline], 5000),
                "open_away_ml": avg_american_odds([book.get("openingLine", {}).get("awayOdds") for book in moneyline], 5000),
                "close_home_spread": avg_number([book.get("currentLine", {}).get("homeSpread") for book in spread]),
                "close_away_spread": avg_number([book.get("currentLine", {}).get("awaySpread") for book in spread]),
                "close_home_spread_odds": avg_american_odds([book.get("currentLine", {}).get("homeOdds") for book in spread], 500),
                "close_away_spread_odds": avg_american_odds([book.get("currentLine", {}).get("awayOdds") for book in spread], 500),
                "close_total": avg_number([book.get("currentLine", {}).get("total") for book in totals]),
                "close_over_odds": avg_american_odds([book.get("currentLine", {}).get("overOdds") for book in totals], 500),
                "close_under_odds": avg_american_odds([book.get("currentLine", {}).get("underOdds") for book in totals], 500),
            }
            index[odds_key(game_date, away, home)] = row
    return index


def american_profit(odds: float) -> float:
    return odds / 100.0 if odds > 0 else 100.0 / abs(odds)


def settle_bet(result: str, odds: float | None) -> float | None:
    if result == "PUSH":
        return 0.0
    if odds is None or result not in {"WIN", "LOSS"}:
        return None
    return american_profit(float(odds)) if result == "WIN" else -1.0


def attach_odds_and_bets(row: dict[str, Any], odds_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    odds = odds_index.get(odds_key(str(row["game_date"]), str(row["away_team"]), str(row["home_team"])), {})
    enriched = {**row, **odds}

    actual_away = float(row["actual_away_runs"])
    actual_home = float(row["actual_home_runs"])
    actual_margin = actual_home - actual_away
    actual_total = actual_home + actual_away
    pred_margin = float(row["pred_home_margin"])
    pred_total = float(row["pred_total_runs"])

    ml_side = "HOME" if float(row["home_win_probability"]) >= 0.5 else "AWAY"
    ml_odds = enriched.get("close_home_ml") if ml_side == "HOME" else enriched.get("close_away_ml")
    ml_result = ""
    if ml_odds is not None:
        ml_result = "WIN" if (actual_margin > 0 and ml_side == "HOME") or (actual_margin < 0 and ml_side == "AWAY") else "LOSS"

    home_spread = enriched.get("close_home_spread")
    away_spread = enriched.get("close_away_spread")
    ats_side = ""
    ats_result = ""
    ats_odds = None
    ats_edge = None
    if home_spread is not None and away_spread is not None:
        home_edge = pred_margin + float(home_spread)
        ats_side = "HOME" if home_edge >= 0 else "AWAY"
        ats_edge = abs(home_edge)
        ats_odds = enriched.get("close_home_spread_odds") if ats_side == "HOME" else enriched.get("close_away_spread_odds")
        side_spread = float(home_spread) if ats_side == "HOME" else float(away_spread)
        side_margin = actual_margin if ats_side == "HOME" else -actual_margin
        ats_cover = side_margin + side_spread
        ats_result = "PUSH" if ats_cover == 0 else "WIN" if ats_cover > 0 else "LOSS"

    close_total = enriched.get("close_total")
    ou_side = ""
    ou_result = ""
    ou_odds = None
    ou_edge = None
    if close_total is not None:
        total_edge = pred_total - float(close_total)
        ou_side = "OVER" if total_edge >= 0 else "UNDER"
        ou_edge = abs(total_edge)
        ou_odds = enriched.get("close_over_odds") if ou_side == "OVER" else enriched.get("close_under_odds")
        ou_delta = actual_total - float(close_total)
        ou_result = "PUSH" if ou_delta == 0 else "WIN" if (ou_delta > 0 and ou_side == "OVER") or (ou_delta < 0 and ou_side == "UNDER") else "LOSS"

    enriched.update(
        {
            "moneyline_pick": ml_side if ml_odds is not None else "",
            "moneyline_close_odds": round(float(ml_odds), 1) if ml_odds is not None else "",
            "moneyline_result": ml_result,
            "moneyline_unit_pnl": round(settle_bet(ml_result, ml_odds), 4) if settle_bet(ml_result, ml_odds) is not None else "",
            "ats_pick": ats_side,
            "ats_edge_runs": round(float(ats_edge), 3) if ats_edge is not None else "",
            "ats_close_odds": round(float(ats_odds), 1) if ats_odds is not None else "",
            "ats_result": ats_result,
            "ats_unit_pnl": round(settle_bet(ats_result, ats_odds), 4) if settle_bet(ats_result, ats_odds) is not None else "",
            "ou_pick": ou_side,
            "ou_edge_runs": round(float(ou_edge), 3) if ou_edge is not None else "",
            "ou_close_odds": round(float(ou_odds), 1) if ou_odds is not None else "",
            "ou_result": ou_result,
            "ou_unit_pnl": round(settle_bet(ou_result, ou_odds), 4) if settle_bet(ou_result, ou_odds) is not None else "",
            "has_odds_history": bool(odds),
            "has_closing_moneyline": ml_odds is not None,
            "has_closing_spread": ats_odds is not None,
            "has_closing_total": ou_odds is not None,
            "has_starting_pitchers": bool(row.get("away_probable_pitcher") and row.get("home_probable_pitcher")),
            "has_lineups": False,
            "has_bullpen_state": False,
            "has_injuries": False,
            "has_weather": False,
        }
    )
    return enriched


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
    def market_summary(prefix: str) -> tuple[int, str, str]:
        pnl_values = [float(row[f"{prefix}_unit_pnl"]) for row in rows if row.get(f"{prefix}_unit_pnl") != ""]
        wins = sum(1 for row in rows if row.get(f"{prefix}_result") == "WIN")
        losses = sum(1 for row in rows if row.get(f"{prefix}_result") == "LOSS")
        decisions = wins + losses
        win_pct = round(wins / decisions, 4) if decisions else ""
        roi = round(sum(pnl_values) / decisions, 4) if decisions else ""
        return decisions, win_pct, roi

    ml_bets, ml_win_pct, ml_roi = market_summary("moneyline")
    ats_bets, ats_win_pct, ats_roi = market_summary("ats")
    ou_bets, ou_win_pct, ou_roi = market_summary("ou")
    odds_games = sum(1 for row in rows if row.get("has_odds_history"))
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
        "odds_games": odds_games,
        "moneyline_bets": ml_bets,
        "moneyline_win_pct": ml_win_pct,
        "moneyline_roi": ml_roi,
        "ats_bets": ats_bets,
        "ats_win_pct": ats_win_pct,
        "ats_roi": ats_roi,
        "ou_bets": ou_bets,
        "ou_win_pct": ou_win_pct,
        "ou_roi": ou_roi,
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
        "odds_games",
        "moneyline_bets",
        "moneyline_win_pct",
        "moneyline_roi",
        "ats_bets",
        "ats_win_pct",
        "ats_roi",
        "ou_bets",
        "ou_win_pct",
        "ou_roi",
    ]
    feature_rows = build_feature_coverage(summary_rows, prediction_sets)
    lines = [
        "# Historical MLB Starter Model Dashboard",
        "",
        f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        *md_table(summary_rows, columns),
        "",
        "## Feature Coverage",
        "",
        *md_table(feature_rows, ["test", "odds_history", "closing_moneyline", "closing_spread", "closing_total", "starting_pitchers", "lineups", "bullpen_state", "injuries", "weather"]),
        "",
        "## Notes",
        "",
        "`2026` includes completed regular-season games available at run time. `2026_through_aug20` is locked through August 20, 2026.",
        "",
        f"Odds history is optional and loads from `{ODDS_PATH.relative_to(REPO_ROOT)}` when present. Source: {ODDS_SOURCE_URL}",
        "",
        "Starting pitcher, lineup, bullpen, injury, and weather coverage are reported explicitly. Missing feature coverage is not imputed.",
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
            "<tr><th>Date</th><th>Away</th><th>Home</th><th>Pred</th><th>Actual</th><th>ML</th><th>ATS</th><th>O/U</th><th>Total Error</th></tr>"
        )
        for row in preview:
            sections.append(
                "<tr>"
                f"<td>{html.escape(str(row['game_date']))}</td>"
                f"<td>{html.escape(str(row['away_team']))}</td>"
                f"<td>{html.escape(str(row['home_team']))}</td>"
                f"<td>{row['pred_away_runs']}-{row['pred_home_runs']}</td>"
                f"<td>{row['actual_away_runs']}-{row['actual_home_runs']}</td>"
                f"<td>{html.escape(str(row.get('moneyline_pick', '')))} {html.escape(str(row.get('moneyline_result', '')))}</td>"
                f"<td>{html.escape(str(row.get('ats_pick', '')))} {html.escape(str(row.get('ats_result', '')))}</td>"
                f"<td>{html.escape(str(row.get('ou_pick', '')))} {html.escape(str(row.get('ou_result', '')))}</td>"
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
    <h2>Feature Coverage</h2>
    <table>{feature_table(feature_rows)}</table>
    {''.join(sections)}
  </main>
</body>
</html>
"""
    (OUT / "dashboard.html").write_text(html_doc, encoding="utf-8")


def pct(count: int, total: int) -> str:
    if total == 0:
        return ""
    return f"{count / total:.1%}"


def build_feature_coverage(summary_rows: list[dict[str, Any]], prediction_sets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    feature_names = [
        ("odds_history", "has_odds_history"),
        ("closing_moneyline", "has_closing_moneyline"),
        ("closing_spread", "has_closing_spread"),
        ("closing_total", "has_closing_total"),
        ("starting_pitchers", "has_starting_pitchers"),
        ("lineups", "has_lineups"),
        ("bullpen_state", "has_bullpen_state"),
        ("injuries", "has_injuries"),
        ("weather", "has_weather"),
    ]
    rows: list[dict[str, Any]] = []
    for summary in summary_rows:
        label = str(summary["test"])
        games = prediction_sets[label]
        total = len(games)
        row = {"test": label}
        for display, key in feature_names:
            row[display] = pct(sum(1 for game in games if game.get(key)), total)
        rows.append(row)
    return rows


def feature_table(rows: list[dict[str, Any]]) -> str:
    columns = ["test", "odds_history", "closing_moneyline", "closing_spread", "closing_total", "starting_pitchers", "lineups", "bullpen_state", "injuries", "weather"]
    table_rows = ["<tr>" + "".join(f"<th>{html.escape(col)}</th>" for col in columns) + "</tr>"]
    for row in rows:
        table_rows.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in columns) + "</tr>")
    return "\n".join(table_rows)


def main() -> int:
    predictor = load_predictor()
    ratings = predictor.load_ratings(RATINGS_PATH)
    odds_index = load_odds_index(ODDS_PATH)
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
        predictions = [attach_odds_and_bets(enrich_prediction(predictor.predict_game(game, ratings)), odds_index) for game in games]
        prediction_sets[label] = predictions
        write_csv(predictions, OUT / filename)
        summary_rows.append(summarize(label, predictions))

    write_csv(summary_rows, OUT / "summary.csv")
    write_dashboard(summary_rows, prediction_sets)
    print(json.dumps({"output_dir": str(OUT), "tests": summary_rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
