from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


HERE = Path(__file__).resolve().parent
DEFAULT_RATINGS = HERE / "team_ratings.csv"
DEFAULT_OUTPUTS = HERE / "outputs"
DEFAULT_MARKET_LINES = HERE / "daily_market_lines.csv"
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}"


@dataclass(frozen=True)
class TeamRating:
    rating: float
    runs_for_pg: float
    runs_allowed_pg: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run tomorrow's MLB starter predictions.")
    parser.add_argument("--date", default=None, help="Prediction date as YYYY-MM-DD. Defaults to tomorrow.")
    parser.add_argument("--ratings", default=DEFAULT_RATINGS, type=Path, help="CSV team rating file.")
    parser.add_argument("--market-lines", default=DEFAULT_MARKET_LINES, type=Path, help="Optional CSV with daily market lines.")
    parser.add_argument("--out-dir", default=DEFAULT_OUTPUTS, type=Path, help="Output folder.")
    parser.add_argument("--offline-sample", action="store_true", help="Use a built-in sample game instead of the MLB API.")
    return parser.parse_args()


def tomorrow_utc() -> date:
    return datetime.now(timezone.utc).date() + timedelta(days=1)


def target_date(value: str | None) -> date:
    if not value:
        return tomorrow_utc()
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_ratings(path: Path) -> dict[str, TeamRating]:
    ratings: dict[str, TeamRating] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ratings[row["team_name"]] = TeamRating(
                rating=float(row["rating"]),
                runs_for_pg=float(row["runs_for_pg"]),
                runs_allowed_pg=float(row["runs_allowed_pg"]),
            )
    return ratings


def normalize_team(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def market_key(day: str, away_team: str, home_team: str) -> str:
    return f"{day}|{normalize_team(away_team)}|{normalize_team(home_team)}"


def parse_optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def american_to_probability(odds: float) -> float:
    return abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)


def load_market_lines(path: Path, day: date) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lines: dict[str, dict[str, Any]] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row_date = row.get("date", day.isoformat()) or day.isoformat()
            if row_date != day.isoformat():
                continue
            away_team = row.get("away_team", "")
            home_team = row.get("home_team", "")
            if not away_team or not home_team:
                continue
            lines[market_key(row_date, away_team, home_team)] = {
                "home_ml": parse_optional_float(row.get("home_ml")),
                "away_ml": parse_optional_float(row.get("away_ml")),
                "home_spread": parse_optional_float(row.get("home_spread")),
                "away_spread": parse_optional_float(row.get("away_spread")),
                "home_spread_odds": parse_optional_float(row.get("home_spread_odds")),
                "away_spread_odds": parse_optional_float(row.get("away_spread_odds")),
                "total": parse_optional_float(row.get("total")),
                "over_odds": parse_optional_float(row.get("over_odds")),
                "under_odds": parse_optional_float(row.get("under_odds")),
            }
    return lines


def fetch_schedule(day: date) -> list[dict[str, Any]]:
    url = SCHEDULE_URL.format(date=day.isoformat())
    try:
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"Could not fetch MLB schedule from {url}: {exc}") from exc

    games: list[dict[str, Any]] = []
    for slate in payload.get("dates", []):
        for game in slate.get("games", []):
            teams = game.get("teams", {})
            away = teams.get("away", {}).get("team", {})
            home = teams.get("home", {}).get("team", {})
            if not away.get("name") or not home.get("name"):
                continue
            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "game_time_utc": game.get("gameDate", ""),
                    "away_team": away["name"],
                    "home_team": home["name"],
                    "status": game.get("status", {}).get("detailedState", ""),
                }
            )
    return games


def sample_schedule() -> list[dict[str, Any]]:
    return [
        {
            "game_pk": "sample_001",
            "game_time_utc": "",
            "away_team": "New York Yankees",
            "home_team": "Boston Red Sox",
            "status": "Sample",
        }
    ]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def predict_game(game: dict[str, Any], ratings: dict[str, TeamRating]) -> dict[str, Any]:
    league = TeamRating(rating=0.0, runs_for_pg=4.45, runs_allowed_pg=4.45)
    home = ratings.get(game["home_team"], league)
    away = ratings.get(game["away_team"], league)
    home_field_runs = 0.12

    home_runs = 0.52 * home.runs_for_pg + 0.48 * away.runs_allowed_pg + home_field_runs
    away_runs = 0.52 * away.runs_for_pg + 0.48 * home.runs_allowed_pg
    home_runs = clamp(home_runs, 2.2, 7.2)
    away_runs = clamp(away_runs, 2.2, 7.2)

    margin = home_runs - away_runs
    rating_margin = home.rating - away.rating + 0.12
    win_prob = 1.0 / (1.0 + math.exp(-(margin * 0.32 + rating_margin * 0.95)))
    total = home_runs + away_runs
    favorite = game["home_team"] if win_prob >= 0.5 else game["away_team"]
    favorite_prob = win_prob if win_prob >= 0.5 else 1.0 - win_prob

    return {
        **game,
        "pred_away_runs": round(away_runs, 2),
        "pred_home_runs": round(home_runs, 2),
        "pred_total_runs": round(total, 2),
        "pred_home_margin": round(margin, 2),
        "home_win_probability": round(win_prob, 4),
        "away_win_probability": round(1.0 - win_prob, 4),
        "favorite": favorite,
        "favorite_probability": round(favorite_prob, 4),
        "model_note": "starter_baseline_not_betting_advice",
    }


def attach_market_edges(row: dict[str, Any], market_lines: dict[str, dict[str, Any]], day: date) -> dict[str, Any]:
    line = market_lines.get(market_key(day.isoformat(), row["away_team"], row["home_team"]), {})
    enriched = {**row, **line}
    pred_margin = float(row["pred_home_margin"])
    pred_total = float(row["pred_total_runs"])

    ml_pick = ""
    ml_edge = ""
    ml_odds = ""
    if line.get("home_ml") is not None and line.get("away_ml") is not None:
        ml_pick = "HOME" if float(row["home_win_probability"]) >= float(row["away_win_probability"]) else "AWAY"
        ml_odds_value = float(line["home_ml"]) if ml_pick == "HOME" else float(line["away_ml"])
        ml_model_prob = float(row["home_win_probability"]) if ml_pick == "HOME" else float(row["away_win_probability"])
        ml_edge = round((ml_model_prob - american_to_probability(ml_odds_value)) * 100.0, 2)
        ml_odds = round(ml_odds_value, 1)

    ats_pick = ""
    ats_edge = ""
    ats_odds = ""
    if line.get("home_spread") is not None and line.get("away_spread") is not None:
        home_edge = pred_margin + float(line["home_spread"])
        ats_pick = "HOME" if home_edge >= 0 else "AWAY"
        ats_edge = round(abs(home_edge), 3)
        odds_value = line.get("home_spread_odds") if ats_pick == "HOME" else line.get("away_spread_odds")
        ats_odds = round(float(odds_value), 1) if odds_value is not None else ""

    ou_pick = ""
    ou_edge = ""
    ou_odds = ""
    if line.get("total") is not None:
        total_edge = pred_total - float(line["total"])
        ou_pick = "OVER" if total_edge >= 0 else "UNDER"
        ou_edge = round(abs(total_edge), 3)
        odds_value = line.get("over_odds") if ou_pick == "OVER" else line.get("under_odds")
        ou_odds = round(float(odds_value), 1) if odds_value is not None else ""

    enriched.update(
        {
            "ml_pick": ml_pick,
            "ml_edge_pct": ml_edge,
            "ml_odds": ml_odds,
            "ats_pick": ats_pick,
            "ats_edge_runs": ats_edge,
            "ats_odds": ats_odds,
            "ou_pick": ou_pick,
            "ou_edge_runs": ou_edge,
            "ou_odds": ou_odds,
            "has_market_lines": bool(line),
        }
    )
    return enriched


def top_edge_bets(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    markets = [
        ("ML", "ml_edge_pct", "ml_pick", "ml_odds"),
        ("ATS", "ats_edge_runs", "ats_pick", "ats_odds"),
        ("OU", "ou_edge_runs", "ou_pick", "ou_odds"),
    ]
    for market, edge_key, pick_key, odds_key in markets:
        eligible = [row for row in rows if row.get(edge_key) != "" and row.get(odds_key) != "" and float(row[edge_key]) > 0]
        ranked = sorted(eligible, key=lambda row: float(row[edge_key]), reverse=True)[:limit]
        if not ranked:
            records.append(
                {
                    "market": market,
                    "rank": "",
                    "away_team": "",
                    "home_team": "",
                    "pick": "NO_MARKET_LINES_OR_POSITIVE_EDGE",
                    "edge": "",
                    "odds": "",
                    "pred_score": "",
                }
            )
            continue
        for rank, row in enumerate(ranked, start=1):
            records.append(
                {
                    "market": market,
                    "rank": rank,
                    "away_team": row["away_team"],
                    "home_team": row["home_team"],
                    "pick": row[pick_key],
                    "edge": row[edge_key],
                    "odds": row[odds_key],
                    "pred_score": f"{row['pred_away_runs']:.2f}-{row['pred_home_runs']:.2f}",
                }
            )
    return records


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return lines


def write_markdown(rows: list[dict[str, Any]], edge_rows: list[dict[str, Any]], path: Path, day: date) -> None:
    lines = [
        f"# MLB Predictions For {day.isoformat()}",
        "",
        "Model: starter baseline",
        "",
    ]
    if not rows:
        lines.append("No MLB games found for this date.")
    else:
        lines.extend(
            [
                "| Away | Home | Pred Score | Favorite | Fav Prob | Total |",
                "| --- | --- | --- | --- | ---: | ---: |",
            ]
        )
        for row in rows:
            lines.append(
                "| {away_team} | {home_team} | {pred_away_runs:.2f}-{pred_home_runs:.2f} | {favorite} | {fav:.1%} | {total:.2f} |".format(
                    away_team=row["away_team"],
                    home_team=row["home_team"],
                    pred_away_runs=row["pred_away_runs"],
                    pred_home_runs=row["pred_home_runs"],
                    favorite=row["favorite"],
                    fav=row["favorite_probability"],
                    total=row["pred_total_runs"],
                )
            )
        lines.extend(
            [
                "",
                "## Top 3 Daily Edge Bets By Market",
                "",
                *markdown_table(edge_rows, ["market", "rank", "away_team", "home_team", "pick", "edge", "odds", "pred_score"]),
            ]
        )
    lines.extend(
        [
            "",
            "Daily edge bets require `daily_market_lines.csv`. If market lines are missing, the edge table shows an explicit no-line placeholder.",
            "",
            "This is a starter model interface. It does not include live odds, injury feeds, pitcher-level projections, or certified bet execution yet.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    day = target_date(args.date)
    ratings = load_ratings(args.ratings)
    market_lines = load_market_lines(args.market_lines, day)
    games = sample_schedule() if args.offline_sample else fetch_schedule(day)
    predictions = [attach_market_edges(predict_game(game, ratings), market_lines, day) for game in games]
    edge_bets = top_edge_bets(predictions)

    out_dir = args.out_dir / day.isoformat()
    csv_path = out_dir / "tomorrow_predictions.csv"
    edges_csv_path = out_dir / "daily_edge_bets.csv"
    markdown_path = out_dir / "tomorrow_predictions.md"
    latest_markdown_path = HERE / "latest_predictions.md"
    write_csv(predictions, csv_path)
    write_csv(edge_bets, edges_csv_path)
    write_markdown(predictions, edge_bets, markdown_path, day)
    write_markdown(predictions, edge_bets, latest_markdown_path, day)
    summary = {
        "date": day.isoformat(),
        "games": len(predictions),
        "games_with_market_lines": sum(1 for row in predictions if row.get("has_market_lines")),
        "csv": str(csv_path),
        "edge_bets_csv": str(edges_csv_path),
        "markdown": str(markdown_path),
        "latest_markdown": str(latest_markdown_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
