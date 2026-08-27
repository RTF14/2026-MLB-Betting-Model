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


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], path: Path, day: date) -> None:
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
            "This is a starter model interface. It does not include live odds, injury feeds, pitcher-level projections, or certified bet execution yet.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    day = target_date(args.date)
    ratings = load_ratings(args.ratings)
    games = sample_schedule() if args.offline_sample else fetch_schedule(day)
    predictions = [predict_game(game, ratings) for game in games]

    out_dir = args.out_dir / day.isoformat()
    write_csv(predictions, out_dir / "tomorrow_predictions.csv")
    write_markdown(predictions, out_dir / "tomorrow_predictions.md", day)
    summary = {
        "date": day.isoformat(),
        "games": len(predictions),
        "csv": str(out_dir / "tomorrow_predictions.csv"),
        "markdown": str(out_dir / "tomorrow_predictions.md"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
