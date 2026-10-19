"""
twitch_recorder.py - records Twitch viewership every 10 minutes, so FSR has a history to score

Twitch's API only says how many people are watching RIGHT NOW. This takes a snapshot each run and
appends it to output/twitch_log/YYYY-MM.csv, building the history Twitch doesn't keep for you:
  - the top 100 live streams (channel, game, viewers)
  - every channel and game in twitch_watch.txt (games: summed viewers of their top 300 streams)

Needs TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env (free app at dev.twitch.tv/console).
register_twitch_task.ps1 runs it every 10 minutes in the background.

Run:
    python twitch_recorder.py                 # one snapshot (what the scheduled task does)
    python twitch_recorder.py --chart xqc     # a channel's viewers at every snapshot it was live
    python twitch_recorder.py --chart "Grand Theft Auto V" --game
    python twitch_recorder.py --top           # who's been biggest, and steadiest, so far
"""
import argparse
import csv
import glob
import json
import os
import statistics
import time
from datetime import datetime, timezone

import requests
from dotenv import dotenv_values

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "output", "twitch_log")
TOKEN_CACHE = os.path.join(HERE, "output", "twitch_token.json")  # app token, not your keys
WATCH = os.path.join(HERE, "twitch_watch.txt")
API = "https://api.twitch.tv/helix"
FIELDS = ["time_utc", "kind", "login", "name", "game", "viewers"]


def creds():
    env = dotenv_values(os.path.join(HERE, ".env"))
    cid, sec = (env.get("TWITCH_CLIENT_ID") or "").strip(), (env.get("TWITCH_CLIENT_SECRET") or "").strip()
    if not cid or not sec:
        raise SystemExit("Put TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env (free app at dev.twitch.tv/console).")
    return cid, sec


def headers():
    """App access token (client credentials), cached until a day before it expires."""
    cid, sec = creds()
    try:
        tok = json.load(open(TOKEN_CACHE))
        if tok.get("client_id") == cid and tok["expires_at"] > time.time() + 86400:
            return {"Client-ID": cid, "Authorization": f"Bearer {tok['access_token']}"}
    except (OSError, ValueError, KeyError):
        pass
    r = requests.post("https://id.twitch.tv/oauth2/token", timeout=30, data={
        "client_id": cid, "client_secret": sec, "grant_type": "client_credentials"})
    r.raise_for_status()
    t = r.json()
    os.makedirs(os.path.dirname(TOKEN_CACHE), exist_ok=True)
    json.dump({"client_id": cid, "access_token": t["access_token"], "expires_at": time.time() + t["expires_in"]},
              open(TOKEN_CACHE, "w"))
    return {"Client-ID": cid, "Authorization": f"Bearer {t['access_token']}"}


def watchlist():
    """twitch_watch.txt: one per line, 'channel: xqc' or 'game: Grand Theft Auto V'."""
    if not os.path.exists(WATCH):
        with open(WATCH, "w", encoding="utf-8") as f:
            f.write("# Twitch recorder watchlist - one per line. Add or remove anytime.\n"
                    "channel: stabilitynetwork\nchannel: kaicenat\nchannel: xqc\nchannel: ishowspeed\n"
                    "channel: zackrawrr\nchannel: summit1g\n"
                    "game: Grand Theft Auto V\ngame: Just Chatting\ngame: Fortnite\ngame: Minecraft\n"
                    "game: Counter-Strike\ngame: Valheim\ngame: Overwatch 2\ngame: TEKKEN 8\n"
                    "game: Science & Technology\n")
    chans, games = [], []
    for line in open(WATCH, encoding="utf-8"):
        kind, _, val = line.strip().partition(":")
        if line.startswith("#") or not val.strip():
            continue
        (chans if kind.strip().lower() == "channel" else games).append(val.strip())
    return chans, games


def snapshot():
    h = headers()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for s in requests.get(f"{API}/streams", headers=h, params={"first": 100}, timeout=30).json().get("data", []):
        rows.append([now, "top", s["user_login"], s["user_name"], s["game_name"], s["viewer_count"]])
    chans, games = watchlist()
    if chans:
        live = {s["user_login"].lower(): s for s in requests.get(
            f"{API}/streams", headers=h, timeout=30, params=[("user_login", c.lower()) for c in chans[:100]]).json().get("data", [])}
        for c in chans:
            s = live.get(c.lower())  # offline channels are recorded as 0 so gaps are visible
            rows.append([now, "channel", c.lower(), s["user_name"] if s else c, s["game_name"] if s else "",
                         s["viewer_count"] if s else 0])
    if games:
        found = requests.get(f"{API}/games", headers=h, timeout=30, params=[("name", g) for g in games[:100]]).json().get("data", [])
        for g in found:
            total, cursor = 0, None
            for _ in range(3):  # top 300 streams of the game
                params = {"game_id": g["id"], "first": 100}
                if cursor:
                    params["after"] = cursor
                js = requests.get(f"{API}/streams", headers=h, params=params, timeout=30).json()
                total += sum(s["viewer_count"] for s in js.get("data", []))
                cursor = (js.get("pagination") or {}).get("cursor")
                if not cursor:
                    break
            rows.append([now, "game", g["id"], g["name"], g["name"], total])
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"{now[:7]}.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(FIELDS)
        w.writerows(rows)
    print(f"{now}: logged {len(rows)} rows to {os.path.relpath(path, HERE)}")


def load():
    rows = []
    for path in sorted(glob.glob(os.path.join(LOG_DIR, "*.csv"))):
        with open(path, encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    return rows


def chart(name, game, k):
    rows = load()
    key = name.lower()
    pick = [r for r in rows if (r["kind"] == "game" and r["name"].lower() == key) if game] if game else \
        [r for r in rows if r["login"].lower() == key and r["kind"] in ("channel", "top")]
    by_time = {}
    for r in pick:  # a watched channel can also appear in the top 100 - keep one reading per snapshot
        by_time[r["time_utc"]] = int(r["viewers"])
    series = [(t, v) for t, v in sorted(by_time.items()) if v > 0]  # live readings only
    if len(series) < 6:
        raise SystemExit(f"Only {len(series)} live readings for '{name}' so far - let the recorder run longer.")
    v = [x for _, x in series]
    hi = v.index(max(v))
    print(f"\n{name}: {len(v)} live snapshots, {series[0][0]} to {series[-1][0]}")
    print(f"Average {statistics.mean(v):,.0f} viewers | peak {v[hi]:,} at {series[hi][0]} | latest {v[-1]:,}")
    print(f"FSR (k={k}) overall {calculate_predictability(v, k):.2f}%  (higher = a steadier audience)")
    slug = "".join(c if c.isalnum() else "_" for c in key).strip("_")
    path = os.path.join(HERE, "output", f"twitch_{'game_' if game else ''}{slug}.txt")
    with open(path, "w") as f:
        f.write(", ".join(str(x) for x in v))
    print(f"Saved {path}  (one point per 10-minute snapshot while live)")


def top_report(k):
    rows = [r for r in load() if r["kind"] in ("top", "channel")]
    per = {}
    for r in rows:
        if int(r["viewers"]) > 0:
            per.setdefault(r["name"], {})[r["time_utc"]] = int(r["viewers"])
    stats = [(n, len(v), statistics.mean(v.values()), calculate_predictability(list(v.values()), k))
             for n, v in per.items() if len(v) >= 12]
    print(f"{'channel':24}{'snapshots':>10}{'avg viewers':>13}{'FSR':>8}")
    for n, c, a, s in sorted(stats, key=lambda t: -t[2])[:25]:
        print(f"{n[:23]:24}{c:>10}{a:>13,.0f}{s:>7.1f}%")


def main():
    p = argparse.ArgumentParser(description="Record Twitch viewership for FSR")
    p.add_argument("--chart", metavar="NAME", help="channel login (or game name with --game) to chart")
    p.add_argument("--game", action="store_true")
    p.add_argument("--top", action="store_true", help="biggest and steadiest channels recorded so far")
    p.add_argument("--k", type=float, default=0.5)
    a = p.parse_args()
    if a.chart:
        chart(a.chart, a.game, a.k)
    elif a.top:
        top_report(a.k)
    else:
        snapshot()


if __name__ == "__main__":
    main()
