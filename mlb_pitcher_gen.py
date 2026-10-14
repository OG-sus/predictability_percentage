#!/usr/bin/env python3
"""mlb_pitcher_gen.py - FSR on a pitcher's raw per-start stats (MLB Stats API, free, no key)

The measurement is the FSR Predictability Score, nothing else: each raw stat from
every start (strikeouts, pitches, outs, batters faced, hits, walks, earned runs) is
fed straight into calculate_predictability. No composite or pre-scored metrics.

Run:
    python mlb_pitcher_gen.py "Cam Schlittler"                 # 2026 season, every raw stat
    python mlb_pitcher_gen.py "Cam Schlittler" --season 2025 --window 5
    python mlb_pitcher_gen.py "Justin Verlander" --career      # every start of the career, 20-start window

Prints each stat's FSR + sliding-window lows and saves every stat's per-start series to
output/<name>_<season|career>_<stat>_per_start.txt, ready to paste into the calculator.
Low-count stats (earned runs, walks) swing hard relative to their small average, so their
lowest windows can land in a pitcher's best stretches - strikeouts/pitches/outs read cleanest.
"""
import argparse
import os
import statistics
from datetime import datetime

import requests

from fsr import calculate_predictability

API = "https://statsapi.mlb.com/api/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
K = 0.5  # sports standard


def find_pitcher(name):
    people = requests.get(f"{API}/people/search", params={"names": name}, timeout=20).json().get("people", [])
    if not people:
        raise SystemExit(f"No MLB player found for '{name}'.")
    return people[0]["id"], people[0]["fullName"]


def starts(pid, season):
    """Every start of a season, regular season plus postseason (gameType P), oldest first.
    The gameLog defaults to regular season only, which left playoff starts out."""
    out = {}
    for game_type in ("R", "P"):
        stats = requests.get(f"{API}/people/{pid}/stats", timeout=20, params={
            "stats": "gameLog", "group": "pitching", "season": season, "gameType": game_type}).json().get("stats", [])
        for s in (stats[0]["splits"] if stats else []):  # injury years come back empty
            if s["stat"].get("gamesStarted"):
                out[s["game"]["gamePk"]] = s
    return sorted(out.values(), key=lambda s: s["date"])


def _outs(stat):
    whole, frac = stat["inningsPitched"].split(".")
    return int(whole) * 3 + int(frac)


RAW_STATS = {  # raw per-start counts, fed straight into FSR
    "strikeouts": lambda t: t["strikeOuts"],
    "pitches": lambda t: t.get("numberOfPitches", 0),
    "outs": _outs,
    "batters_faced": lambda t: t["battersFaced"],
    "hits": lambda t: t["hits"],
    "walks": lambda t: t["baseOnBalls"],
    "earned_runs": lambda t: t["earnedRuns"],
}


def report(games, label, slug, window):
    """FSR on every raw stat; save each stat's series for the calculator."""
    if len(games) < window + 2:
        raise SystemExit(f"Only {len(games)} starts - not enough for a window of {window}.")
    dates = [g["date"] for g in games]
    os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
    print(f"\n{label}: {len(games)} starts, {dates[0]} to {dates[-1]} (FSR k={K}, window {window})\n")
    print(f"{'raw stat':<15}{'avg/start':>10}{'FSR':>9}{'window typical':>16}{'lowest':>9}  lowest window ends")
    for name, fn in RAW_STATS.items():
        v = [fn(g["stat"]) for g in games]
        if not any(v):
            continue
        roll = [calculate_predictability(v[i - window:i], K) for i in range(window, len(v) + 1)]
        print(f"{name:<15}{statistics.mean(v):>10.1f}{calculate_predictability(v, K):>8.1f}%"
              f"{statistics.median(roll):>15.1f}%{min(roll):>8.1f}%  {dates[roll.index(min(roll)) + window - 1]}")
        with open(os.path.join(HERE, "output", f"{slug}_{name}_per_start.txt"), "w") as f:
            f.write(", ".join(map(str, v)))
    print(f"\nSaved output/{slug}_<stat>_per_start.txt for each stat - paste one into the calculator.")


def main():
    parser = argparse.ArgumentParser(description="FSR on an MLB pitcher's raw per-start stats")
    parser.add_argument("name", help='pitcher name, e.g. "Cam Schlittler"')
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--career", action="store_true", help="every start of the career (regular season + postseason)")
    parser.add_argument("--window", type=int, help="sliding window in starts (default 5 season / 20 career)")
    args = parser.parse_args()

    pid, full = find_pitcher(args.name)
    base = full.lower().replace(" ", "_")
    if args.career:
        info = requests.get(f"{API}/people/{pid}", timeout=20).json()["people"][0]
        first = int(info.get("mlbDebutDate", "2000")[:4])
        last = int(info.get("lastPlayedDate", str(datetime.now().year))[:4])
        games = [g for year in range(first, last + 1) for g in starts(pid, year)]
        report(games, f"{full} - career", f"{base}_career", args.window or 20)
    else:
        report(starts(pid, args.season), f"{full} - {args.season}", f"{base}_{args.season}", args.window or 5)


if __name__ == "__main__":
    main()
