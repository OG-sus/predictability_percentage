"""
daily_slate.py — FSR Daily MLB Slate Generator
===============================================
Runs every morning via cron. Pulls today's MLB schedule from the
MLB Stats API (free, no key needed), then generates:
  - Pitcher K-rate FSR matchup chart per game
  - Pitcher GB% consistency chart per game
  - Park HR factor chart per game
  - City VPD weather chart per game (outdoor stadiums only)
  - FSR starter leaderboard summary chart

Output: static/images/mlb_preview/YYYY/MM-DD/

Usage:
    python daily_slate.py               # today
    python daily_slate.py 2026-05-10    # specific date

Cron (9am ET = 1pm UTC):
    0 13 * * * cd /root/predictability_percentage && source venv/bin/activate && python3 daily_slate.py >> /root/logs/daily_slate.log 2>&1
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── MLB Stats API (free, no key) ──────────────────────────────────────────────
MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"

# ── Dome/retractable roof stadiums — skip VPD chart ──────────────────────────
DOME_PARKS = {
    "American Family Field",
    "Daikin Park",
    "T-Mobile Park",
    "Globe Life Field",
    "Rogers Centre",
    "Tropicana Field",
    "Chase Field",
    "loanDepot park",
    "Minute Maid Park",
}

# ── Team → home city (for VPD lookup) ────────────────────────────────────────
TEAM_CITY = {
    "NYY": "New York",     "NYM": "New York",     "BOS": "Boston",
    "TOR": "Toronto",      "BAL": "Baltimore",    "TB":  "Tampa",
    "CLE": "Cleveland",    "DET": "Detroit",      "CWS": "Chicago",
    "MIN": "Minneapolis",  "KC":  "Kansas City",  "HOU": "Houston",
    "LAA": "Los Angeles",  "OAK": "Oakland",      "ATH": "Sacramento",
    "TEX": "Dallas",       "SEA": "Seattle",      "ATL": "Atlanta",
    "PHI": "Philadelphia", "MIA": "Miami",        "WSH": "Washington",
    "MIL": "Milwaukee",    "CHC": "Chicago",      "STL": "St. Louis",
    "CIN": "Cincinnati",   "PIT": "Pittsburgh",   "LAD": "Los Angeles",
    "SF":  "San Francisco","SD":  "San Diego",    "COL": "Denver",
    "ARI": "Phoenix",
}


# ── MLB Stats API: fetch schedule ─────────────────────────────────────────────

def fetch_mlb_schedule(game_date: date) -> list[dict]:
    """
    Fetches the MLB schedule for game_date from the free MLB Stats API.
    Returns a list of game dicts compatible with mlb_326_2026_graphs.py.
    """
    date_str = game_date.strftime("%Y-%m-%d")
    logging.info(f"Fetching MLB schedule for {date_str}...")

    try:
        r = requests.get(MLB_SCHEDULE_URL, params={
            "sportId": 1,
            "date":    date_str,
            "hydrate": "probablePitcher,team,venue",
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logging.error(f"Failed to fetch schedule: {e}")
        return []

    dates = data.get("dates", [])
    if not dates:
        logging.warning(f"No games found for {date_str}")
        return []

    games = []
    for game in dates[0].get("games", []):
        try:
            away_team    = game["teams"]["away"]["team"]
            home_team    = game["teams"]["home"]["team"]
            venue        = game.get("venue", {})
            away_abbr    = away_team.get("abbreviation", "UNK")
            home_abbr    = home_team.get("abbreviation", "UNK")
            park_name    = venue.get("name", "Unknown Park")
            city         = TEAM_CITY.get(home_abbr, home_team.get("locationName", "Unknown"))

            away_pitcher = game["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD")
            home_pitcher = game["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD")

            # Convert UTC game time → ET
            game_time = game.get("gameDate", "")
            try:
                dt      = datetime.strptime(game_time, "%Y-%m-%dT%H:%M:%SZ")
                et_hour = (dt.hour - 4) % 24
                ampm    = "AM" if et_hour < 12 else "PM"
                time_et = f"{et_hour % 12 or 12}:{dt.minute:02d} {ampm} ET"
            except Exception:
                time_et = "TBD"

            games.append({
                "away":         away_abbr,
                "home":         home_abbr,
                "away_pitcher": away_pitcher,
                "home_pitcher": home_pitcher,
                "park":         park_name,
                "city":         city,
                "is_dome":      park_name in DOME_PARKS,
                "time_et":      time_et,
            })
        except Exception as e:
            logging.warning(f"Skipping malformed game entry: {e}")
            continue

    logging.info(f"Found {len(games)} games on {date_str}")
    return games


# ── Main ──────────────────────────────────────────────────────────────────────

def run_daily_slate(game_date: date | None = None) -> list[str]:
    target    = game_date or date.today()
    date_str  = target.strftime("%Y-%m-%d")
    month_day = target.strftime("%m-%d")
    year_str  = target.strftime("%Y")

    logging.info(f"\n{'='*60}")
    logging.info(f"  FSR Daily MLB Slate  |  {date_str}")
    logging.info(f"{'='*60}\n")

    games = fetch_mlb_schedule(target)
    if not games:
        logging.warning("No games today or schedule unavailable.")
        return []

    # Log today's full slate
    for i, g in enumerate(games, 1):
        dome = " [DOME]" if g["is_dome"] else ""
        logging.info(
            f"  {i:2d}. {g['away']} @ {g['home']}  {g['time_et']:>12}{dome}\n"
            f"      {g['away_pitcher']} vs {g['home_pitcher']}"
        )
    logging.info("")

    # Only generate charts for confirmed starters
    chartable = [g for g in games if g["away_pitcher"] != "TBD" and g["home_pitcher"] != "TBD"]
    tbd = len(games) - len(chartable)
    if tbd:
        logging.info(f"  {tbd} game(s) skipped — TBD starters\n")

    # Import and patch mlb_326_2026_graphs
    try:
        import mlb_326_2026_graphs as mlb326
    except ImportError:
        logging.error("mlb_326_2026_graphs.py not found in project directory.")
        return []

    out_dir = os.path.join("static", "images", "mlb_preview", year_str, month_day)
    os.makedirs(out_dir, exist_ok=True)

    # Patch module-level variables so chart functions use today's context
    mlb326.OUTPUT_DIR   = out_dir
    mlb326.GAMES        = chartable
    mlb326.SEASON_START = f"{target.year}-03-01"
    mlb326.SEASON_END   = date_str

    logging.info(f"  Output dir  : {out_dir}")
    logging.info(f"  Statcast    : {mlb326.SEASON_START} → {mlb326.SEASON_END}")
    logging.info(f"  Games       : {len(chartable)} with confirmed starters\n")

    generated: list[str] = []
    results:   list[dict] = []

    for i, game in enumerate(chartable, 1):
        away, home = game["away"], game["home"]
        logging.info(f"[{i}/{len(chartable)}]  {away} @ {home}  —  {game['time_et']}")
        result: dict = {"game": game, "away_fsr": None, "home_fsr": None}

        for fn_name, label in [
            ("save_pitcher_matchup_chart", "Pitcher K-rate "),
            ("save_pitcher_gbfb_chart",    "Pitcher GB%    "),
            ("save_park_context_chart",    "Park HR        "),
        ]:
            try:
                fn = getattr(mlb326, fn_name)
                p  = fn(game)
                generated.append(p)
                logging.info(f"   + {label} → {os.path.basename(p)}")
            except Exception as e:
                logging.warning(f"   x {label} failed: {e}")

        # VPD weather — outdoor only
        if not game.get("is_dome"):
            try:
                p = mlb326.save_city_vpd_chart(game, target)
                if p:
                    generated.append(p)
                    logging.info(f"   + VPD           → {os.path.basename(p)}")
            except Exception as e:
                logging.warning(f"   x VPD failed: {e}")

        results.append(result)

    # FSR leaderboard summary
    try:
        p = mlb326.save_fsr_summary_chart(results)
        if p:
            generated.append(p)
            logging.info(f"\n   + FSR leaderboard → {os.path.basename(p)}")
    except Exception as e:
        logging.warning(f"   x Leaderboard failed: {e}")

    logging.info(f"\n{'='*60}")
    logging.info(f"  Done — {len(generated)} charts saved")
    logging.info(f"{'='*60}\n")
    return generated


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    target_date = None
    if len(sys.argv) > 1:
        try:
            target_date = date.fromisoformat(sys.argv[1])
        except ValueError:
            logging.error(f"Bad date format: {sys.argv[1]}. Use YYYY-MM-DD.")
            sys.exit(1)

    paths = run_daily_slate(target_date)
    print(f"\nGenerated {len(paths)} charts.")
    for p in paths:
        print(f"  {p}")