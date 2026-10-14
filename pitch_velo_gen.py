"""
pitch_velo_gen.py - every pitch of one type a pitcher threw (or every ball a hitter hit), for FSR

The "every slider / every fastball" Shorts. Pulls each game of the season from the MLB Stats API
(free, no key) and saves the raw speed of every pitch of the chosen type, in order. The default
window is about one start's worth of that pitch. Sports standard: k=0.5.

Pitch type codes: FF four-seam, SI sinker, FC cutter, SL slider, ST sweeper, CU curve,
KC knuckle-curve, CH changeup, FS splitter.

Run:
    python pitch_velo_gen.py "Chris Sale"                    # lists his pitch mix, then uses his most-thrown pitch
    python pitch_velo_gen.py "Chris Sale" --pitch SL
    python pitch_velo_gen.py "Munetaka Murakami" --hitter    # exit velocity of every batted ball
    python pitch_velo_gen.py "Drew Rasmussen" --pitch FC --season 2026
"""
import argparse
import os
import statistics
from collections import Counter

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://statsapi.mlb.com/api/v1"


def player_id(name):
    people = requests.get(f"{API}/people/search", params={"names": name}, timeout=30).json().get("people", [])
    if not people:
        raise SystemExit(f"No MLB player found for '{name}'.")
    return people[0]["id"], people[0]["fullName"]


def games(pid, season, group):
    """Regular season plus postseason (gameType P), oldest first. The gameLog defaults to regular
    season only, which left a pitcher's playoff starts - the whole reason for the Short - out."""
    out = {}
    for game_type in ("R", "P"):
        stats = requests.get(f"{API}/people/{pid}/stats", params={
            "stats": "gameLog", "group": group, "season": season, "gameType": game_type}, timeout=30).json()["stats"]
        for g in (stats[0]["splits"] if stats else []):
            out[g["game"]["gamePk"]] = g
    return sorted(out.values(), key=lambda g: g["date"])


def main():
    p = argparse.ArgumentParser(description="Every pitch (or batted ball) of a player's season, for FSR")
    p.add_argument("name")
    p.add_argument("--pitch", help="pitch type code (default: his most-thrown pitch)")
    p.add_argument("--hitter", action="store_true", help="exit velocity of every batted ball instead")
    p.add_argument("--season", type=int, default=2026)
    p.add_argument("--k", type=float, default=0.5)
    a = p.parse_args()

    pid, full = player_id(a.name)
    gl = games(pid, a.season, "hitting" if a.hitter else "pitching")
    if not gl:
        raise SystemExit(f"No {a.season} games for {full}.")
    rows = []  # (date, type, speed)
    print(f"{full}: reading {len(gl)} games...")
    for g in gl:
        feed = requests.get(f"https://statsapi.mlb.com/api/v1.1/game/{g['game']['gamePk']}/feed/live",
                            timeout=60).json()
        for play in feed["liveData"]["plays"]["allPlays"]:
            who = play["matchup"]["batter" if a.hitter else "pitcher"]["id"]
            if who != pid:
                continue
            for ev in play["playEvents"]:
                if a.hitter:
                    speed = (ev.get("hitData") or {}).get("launchSpeed")
                    if speed:
                        rows.append((g["date"], play["result"].get("eventType", ""), speed))
                elif ev.get("isPitch") and (ev.get("pitchData") or {}).get("startSpeed"):
                    rows.append((g["date"], ev["details"].get("type", {}).get("code"), ev["pitchData"]["startSpeed"]))

    if a.hitter:
        chosen, label = rows, "batted balls (exit velocity)"
    else:
        mix = Counter(t for _, t, _ in rows)
        print("Pitch mix: " + ", ".join(f"{t} {n}" for t, n in mix.most_common()))
        code = a.pitch or mix.most_common(1)[0][0]
        chosen, label = [r for r in rows if r[1] == code], f"{code} pitches"
    v = [s for _, _, s in chosen]
    d = [day for day, _, _ in chosen]
    if len(v) < 30:
        raise SystemExit(f"Only {len(v)} {label} - too few to chart.")
    window = max(10, round(len(v) / len(gl)))  # about one game's worth

    by_game = {}
    for day, _, s in chosen:
        by_game.setdefault(day, []).append(s)
    avgs = [(day, statistics.mean(x)) for day, x in by_game.items()]
    slow, fast = min(avgs, key=lambda x: x[1]), max(avgs, key=lambda x: x[1])
    print(f"\n{full}, {a.season}: {len(v)} {label} over {len(gl)} games")
    print(f"Average {statistics.mean(v):.1f} mph | max {max(v):.1f} ({d[v.index(max(v))]}) | "
          f"slowest game avg {slow[1]:.1f} ({slow[0]}) | fastest game avg {fast[1]:.1f} ({fast[0]})")
    print("Last 3 games: " + ", ".join(f"{day} {s:.1f}" for day, s in avgs[-3:]))
    r = [calculate_predictability(v[i - window:i], a.k) for i in range(window, len(v) + 1)]
    e = d[window - 1:]
    print(f"FSR (k={a.k}) whole season {calculate_predictability(v, a.k):.2f}% | window {window} (~1 game): "
          f"lowest {min(r):.2f}% ({e[r.index(min(r))]}), highest {max(r):.2f}% ({e[r.index(max(r))]}), "
          f"latest {r[-1]:.2f}%")

    slug = full.lower().replace(" ", "_").replace(".", "")
    tag = "exit_velo" if a.hitter else f"{chosen[0][1]}_velo"
    path = os.path.join(HERE, "output", f"{slug}_{a.season}_{tag}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{x:g}" for x in v))
    print(f"\nSaved {path}  (chart it at window {window}, k={a.k})")


if __name__ == "__main__":
    main()
