"""mlb_daily.py
==============
Season launcher for daily MLB FSR chart generation.
Edit the CONFIG section each morning, then run:

    python mlb_daily.py
    python mlb_daily.py --date 2026-03-28
    python mlb_daily.py --date 2026-03-28 --skip-batters
    python mlb_daily.py --date 2026-03-28 --force-park
    python mlb_daily.py --date 2026-03-28 --only weather
    python mlb_daily.py --date 2026-03-28 --only pitchers
    python mlb_daily.py --date 2026-03-28 --only batters

What regenerates daily (always):
  • Pitcher K-rate + GB% matchup charts   (new starters every day)
  • VPD weather charts                    (weather changes daily)
  • Batter duel charts                    (if listed in BATTER_MATCHUPS)
  • Closer duel charts                    (if listed in CLOSER_DUELS)

What stays cached (skipped if file exists):
  • Park HR context charts                (park factors don't change mid-season)
  • Use --force-park to regenerate anyway

Output: static/images/mlb_preview/{year}/{MM-DD}/
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date as Date

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# ===============================================================================
#  DAILY CONFIG ─ edit this section each morning
#  Copy the block from the previous day and update starters + date.
# ===============================================================================

GAME_DATE = "2026-03-29"   # ← change this every day

# One dict per game. Dome stadiums get no weather chart automatically.
GAMES: list[dict] = [
    {
        "away": "MIN",  "home": "BAL",
        "away_pitcher": "Bailey Ober",            "home_pitcher": "Shane Baz",
        "park": "Oriole Park at Camden Yards",    "city": "Baltimore",
        "is_dome": False,                         "time_et": "1:35 PM",
    },
    {
        "away": "TEX",  "home": "PHI",
        "away_pitcher": "MacKenzie Gore",         "home_pitcher": "Jesus Luzardo",
        "park": "Citizens Bank Park",             "city": "Philadelphia",
        "is_dome": False,                         "time_et": "1:35 PM",
    },
    {
        "away": "KC",   "home": "ATL",
        "away_pitcher": "Seth Lugo",              "home_pitcher": "Grant Holmes",
        "park": "Truist Park",                    "city": "Atlanta",
        "is_dome": False,                         "time_et": "1:35 PM",
    },
    {
        "away": "ATH",  "home": "TOR",
        "away_pitcher": "Luis Morales",           "home_pitcher": "Eric Lauer",
        "park": "Rogers Centre",                  "city": "Toronto",
        "is_dome": True,                          "time_et": "1:37 PM",
    },
    {
        "away": "BOS",  "home": "CIN",
        "away_pitcher": "Connelly Early",         "home_pitcher": "Rhett Lowder",
        "park": "Great American Ball Park",       "city": "Cincinnati",
        "is_dome": False,                         "time_et": "1:40 PM",
    },
    {
        "away": "PIT",  "home": "NYM",
        "away_pitcher": "Carmen Mlodzinski",      "home_pitcher": "Nolan McLean",
        "park": "Citi Field",                     "city": "New York",
        "is_dome": False,                         "time_et": "1:40 PM",
    },
    {
        "away": "COL",  "home": "MIA",
        "away_pitcher": "Jose Quintana",          "home_pitcher": "Max Meyer",
        "park": "loanDepot Park",                 "city": "Miami",
        "is_dome": True,                          "time_et": "1:40 PM",
    },
    {
        "away": "LAA",  "home": "HOU",
        "away_pitcher": "Jack Kochanowicz",       "home_pitcher": "Tatsuya Imai",
        "park": "Daikin Park",                    "city": "Houston",
        "is_dome": True,                          "time_et": "2:10 PM",
    },
    {
        "away": "CWS",  "home": "MIL",
        "away_pitcher": "Anthony Kay",            "home_pitcher": "Brandon Sproat",
        "park": "American Family Field",          "city": "Milwaukee",
        "is_dome": True,                          "time_et": "2:10 PM",
    },
    {
        "away": "TB",   "home": "STL",
        "away_pitcher": "Dustin May",             "home_pitcher": "Steven Matz",
        "park": "Busch Stadium",                  "city": "St. Louis",
        "is_dome": False,                         "time_et": "2:15 PM",
    },
    {
        "away": "WSH",  "home": "CHC",
        "away_pitcher": "Jake Irvin",             "home_pitcher": "Shota Imanaga",
        "park": "Wrigley Field",                  "city": "Chicago",
        "is_dome": False,                         "time_et": "2:20 PM",
    },
    {
        "away": "CLE",  "home": "SEA",
        "away_pitcher": "Slade Cecconi",          "home_pitcher": "Emerson Hancock",
        "park": "T-Mobile Park",                  "city": "Seattle",
        "is_dome": True,                          "time_et": "7:20 PM",
    },
]

# Batter matchup charts — leave empty list to skip for a game.
# Each entry produces one chart per stat listed.
BATTER_MATCHUPS: list[dict] = [
    {
        "away": "TEX",  "home": "PHI",
        "away_batters": ["corey seager", "marcus semien", "nathaniel lowe"],
        "home_batters":  ["bryce harper", "kyle schwarber", "trea turner"],
        "stats": ["H"],
        "num_games": 40,
    },
    {
        "away": "KC",   "home": "ATL",
        "away_batters": ["bobby witt jr", "salvador perez", "vinnie pasquantino"],
        "home_batters":  ["ozzie albies", "michael harris ii", "matt olson"],
        "stats": ["H"],
        "num_games": 40,
    },
]

STAR_CHARTS: list[dict] = [
    # MacKenzie Gore spotlight -- TEX @ PHI
    {
        "name": "mackenzie gore",  "team": "TEX",
        "stats": ["SO"],
        "game_label": "TEX @ PHI  .  Citizens Bank Park  .  1:35 PM ET",
        "num_games": 30,
    },
    # Shota Imanaga spotlight -- WSH @ CHC
    {
        "name": "shota imanaga",  "team": "CHC",
        "stats": ["SO"],
        "game_label": "WSH @ CHC  .  Wrigley Field  .  2:20 PM ET",
        "num_games": 30,
    },
]

CLOSER_DUELS: list[dict] = [
    {
        "away": "TEX",  "home": "PHI",
        "away_closer": "jose leclerc",
        "home_closer": "jeff hoffman",
        "stat": "K",
        "num_games": 40,
    },
    {
        "away": "KC",   "home": "ATL",
        "away_closer": "james mcarthur",
        "home_closer": "raisel iglesias",
        "stat": "K",
        "num_games": 40,
    },
]

# Bullpen matchup charts — list 2-3 key relievers per team.
# Produces one combined FSR chart per entry.
BULLPEN_DUELS: list[dict] = [
    {
        "away": "TEX",  "home": "PHI",
        "away_relievers": ["jose leclerc", "jonathan hernandez", "kirby yates"],
        "home_relievers": ["seranthony dominguez", "jeff hoffman", "jose alvarado"],
        "stat": "K",
        "num_games": 35,
    },
    {
        "away": "CLE",  "home": "SEA",
        "away_relievers": ["cade smith", "hunter gaddis", "tim herrin"],
        "home_relievers": ["andres munoz", "trent thornton", "matt brash"],
        "stat": "K",
        "num_games": 35,
    },
]

# ===============================================================================
#  END CONFIG — nothing below needs editing for daily use
# ===============================================================================


def _out_dir(game_date: str) -> str:
    year = game_date[:4]
    mm_dd = game_date[5:].replace("-", "-")
    path = os.path.join("static", "images", "mlb_preview", year, mm_dd)
    os.makedirs(path, exist_ok=True)
    return path


def _slug(game: dict) -> str:
    return f"{game['away'].lower()}_{game['home'].lower()}"


def _import_graph_module():
    """Import mlb_326_2026_graphs but patch its OUTPUT_DIR + GAME_DATE_STR."""
    import importlib
    import mlb_326_2026_graphs as g
    return g


def run(game_date: str, only: str | None, force_park: bool, skip_batters: bool):
    out_dir = _out_dir(game_date)
    target  = Date.fromisoformat(game_date)
    generated: list[str] = []
    skipped:   list[str] = []

    # ── Patch the graph module's output dir and game date ─────────────────────
    import mlb_326_2026_graphs as G
    G.OUTPUT_DIR     = out_dir
    G.GAME_DATE_STR  = game_date

    # ── Import batter chart functions ─────────────────────────────────────────
    from batter_fsr_charts import (
        build_batter_duel_chart,
        build_solo_batter_chart,
        build_closer_duel_chart,
        build_bullpen_chart,
    )

    total_games = len(GAMES)
    logging.info(f"=== MLB Daily  {game_date}  .  {total_games} games  .  output → {out_dir}")

    # ──────────────────────────────────────────────────────────────────────────
    # 1. PITCHER charts (always regenerated)
    # ──────────────────────────────────────────────────────────────────────────
    if only in (None, "pitchers"):
        logging.info("── Pitcher charts ──────────────────────────────────────")
        for i, game in enumerate(GAMES, 1):
            slug = _slug(game)
            game_copy = dict(game)
            game_copy["out_dir"] = out_dir          # used by save_* functions

            logging.info(f"  [{i}/{total_games}] {game['away']} @ {game['home']}")

            # Patch per-game output path used inside mlb_326_2026_graphs
            pitcher_path = os.path.join(out_dir, f"pitcher_{slug}.png")
            gbfb_path    = os.path.join(out_dir, f"gbfb_{slug}.png")

            try:
                G.save_pitcher_matchup_chart(game_copy)
                generated.append(pitcher_path)
            except Exception as e:
                logging.error(f"    Pitcher chart failed: {e}")

            try:
                G.save_pitcher_gbfb_chart(game_copy)
                generated.append(gbfb_path)
            except Exception as e:
                logging.warning(f"    GB/FB chart failed (may need more data): {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. WEATHER/VPD charts (always regenerated, outdoor only)
    # ──────────────────────────────────────────────────────────────────────────
    if only in (None, "weather"):
        logging.info("── Weather/VPD charts ──────────────────────────────────")
        outdoor_games = [g for g in GAMES if not g.get("is_dome", False)]
        dome_count    = len(GAMES) - len(outdoor_games)
        if dome_count:
            logging.info(f"  Skipping {dome_count} dome stadium(s)")

        for game in outdoor_games:
            logging.info(f"  VPD: {game['city']}")
            try:
                path = G.save_city_vpd_chart(game, end_date=target)
                if path:
                    generated.append(path)
            except Exception as e:
                logging.error(f"    VPD chart failed for {game['city']}: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. PARK context charts (cached — skip if file already exists)
    # ──────────────────────────────────────────────────────────────────────────
    if only in (None, "parks"):
        logging.info("── Park context charts ─────────────────────────────────")
        for game in GAMES:
            slug = _slug(game)
            park_path = os.path.join(out_dir, f"park_{game['home'].lower()}.png")

            if os.path.exists(park_path) and not force_park:
                skipped.append(park_path)
                logging.info(f"  CACHED  {os.path.basename(park_path)}")
                continue

            try:
                G.save_park_context_chart(game)
                generated.append(park_path)
            except Exception as e:
                logging.error(f"    Park chart failed for {game['home']}: {e}")

            # Optional: also generate away team's home park (e.g. Coors Field for COL on road)
            if game.get("away_park_context"):
                away_park_path = os.path.join(out_dir, f"park_{game['away'].lower()}_home.png")
                if not os.path.exists(away_park_path) or force_park:
                    away_game = dict(game)
                    away_game["home"] = game["away"]     # swap so save_park_context_chart uses away team's park
                    try:
                        G.save_park_context_chart(away_game, out_path_override=away_park_path)
                        generated.append(away_park_path)
                        logging.info(f"  Away park context: {game['away']} home park")
                    except Exception as e:
                        logging.warning(f"    Away park context failed: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. BATTER duel charts
    # ──────────────────────────────────────────────────────────────────────────
    if only in (None, "batters") and not skip_batters:
        logging.info("── Batter duel charts ──────────────────────────────────")
        for m in BATTER_MATCHUPS:
            away, home = m["away"], m["home"]
            for stat in m.get("stats", ["H"]):
                out_path = os.path.join(out_dir,
                    f"batter_duel_{away.lower()}_{home.lower()}_{stat.lower()}.png")
                logging.info(f"  {away} @ {home}  stat={stat}")
                try:
                    build_batter_duel_chart(
                        game_label=f"{away} @ {home}  {game_date}",
                        away_team=away, away_batters=m["away_batters"],
                        home_team=home, home_batters=m["home_batters"],
                        stat=stat,
                        num_games=m.get("num_games", 40),
                        out_path=out_path,
                        title_suffix=f"{game_date}",
                    )
                    generated.append(out_path)
                except Exception as e:
                    logging.error(f"    Batter duel failed: {e}")

        # Star charts
        for s in STAR_CHARTS:
            out_path = os.path.join(out_dir,
                f"star_{s['name'].replace(' ','_')}_{game_date}.png")
            logging.info(f"  Star chart: {s['name']}")
            try:
                build_solo_batter_chart(
                    name=s["name"], team=s["team"],
                    stats=s.get("stats", ["H", "HR"]),
                    game_label=s.get("game_label", ""),
                    num_games=s.get("num_games", 50),
                    out_path=out_path,
                )
                generated.append(out_path)
            except Exception as e:
                logging.error(f"    Star chart failed: {e}")

        # Closer duels
        for c in CLOSER_DUELS:
            out_path = os.path.join(out_dir,
                f"closer_{c['away'].lower()}_{c['home'].lower()}.png")
            logging.info(f"  Closer duel: {c['away']} @ {c['home']}")
            try:
                build_closer_duel_chart(
                    game_label=f"{c['away']} @ {c['home']}  {game_date}",
                    away_team=c["away"], away_closer=c["away_closer"],
                    home_team=c["home"], home_closer=c["home_closer"],
                    stat=c.get("stat", "K"),
                    num_games=c.get("num_games", 40),
                    out_path=out_path,
                )
                generated.append(out_path)
            except Exception as e:
                logging.error(f"    Closer duel failed: {e}")

        # Bullpen duels
        logging.info("-- Bullpen duel charts -----------------------------------------")
        for b in BULLPEN_DUELS:
            away, home = b["away"], b["home"]
            out_path = os.path.join(out_dir,
                f"bullpen_{away.lower()}_{home.lower()}.png")
            logging.info(f"  Bullpen: {away} @ {home}")
            try:
                build_bullpen_chart(
                    game_label=f"{away} @ {home}  {game_date}",
                    away_team=away, away_relievers=b["away_relievers"],
                    home_team=home,  home_relievers=b["home_relievers"],
                    stat=b.get("stat", "K"),
                    num_games=b.get("num_games", 35),
                    out_path=out_path,
                )
                generated.append(out_path)
            except Exception as e:
                logging.error(f"    Bullpen chart failed: {e}")

    # FSR Summary leaderboard — skipped (mlb_326 hardcoded games would overwrite daily charts)

    # ── Final report ──────────────────────────────────────────────────────────
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  MLB Daily  {game_date}  --  DONE")
    print(f"  Generated : {len(generated)} charts")
    print(f"  Cached    : {len(skipped)} park charts (use --force-park to regen)")
    print(f"  Output    : {out_dir}")
    print(sep)
    for p in generated:
        print(f"  +  {os.path.basename(p)}")
    if skipped:
        print(f"\n  Cached (skipped):")
        for p in skipped:
            print(f"  ~  {os.path.basename(p)}")
    print()


def main():
    parser = argparse.ArgumentParser(description="MLB Daily FSR Chart Generator")
    parser.add_argument("--date",         default=GAME_DATE,
                        help="Game date YYYY-MM-DD (default: GAME_DATE in config)")
    parser.add_argument("--only",         choices=["pitchers","weather","parks","batters"],
                        default=None,
                        help="Generate only one chart type")
    parser.add_argument("--force-park",   action="store_true",
                        help="Regenerate park charts even if cached")
    parser.add_argument("--skip-batters", action="store_true",
                        help="Skip batter/closer charts (faster run)")
    args = parser.parse_args()

    run(
        game_date    = args.date,
        only         = args.only,
        force_park   = args.force_park,
        skip_batters = args.skip_batters,
    )


if __name__ == "__main__":
    main()
