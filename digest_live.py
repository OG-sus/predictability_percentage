"""
digest_live.py - "what's happening now" scans that RUN the generators, for morning_digest.py

Every scan returns ready-to-chart items: the generator has already saved the series file, and
the item carries the settings, the headline numbers and a search phrase. The digest then scores
each item's virality (Wikipedia attention spike + YouTube rising searches) and puts the best at
the top as "Ready to chart".

    Earth / NASA : big quakes (every quake near the epicenter), fire seasons (NASA FIRMS),
                   giant ocean waves (NOAA buoys), drought spreading (Drought Monitor),
                   flu rising (CDC), tornado outbreaks (SPC), groundwater record lows (NASA)
    Sports       : tonight's + tomorrow's MLB starters (every pitch), NBA stars playing
                   (game by game), NFL primetime games (listed)

Each scan is independent and time-boxed; a failing source just drops out.
"""
import json
import os
import re
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "predictability-api.com digest"}
PY = sys.executable


def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def item(kind, title, why, cmd, out=None, query=None, keywords=(), broken=False):
    """One ready-to-chart (or ready-to-run) idea. keywords = SPECIFIC names (a place, a person)
    used to match YouTube rising searches - generic words like "earthquake" matched everything.
    broken = the chart has zero stretches that break FSR, so it stays out of 'Ready to chart'."""
    return {"kind": kind, "title": title, "why": why, "cmd": cmd, "out": out or {},
            "query": query or title, "keywords": [k.lower() for k in keywords], "viral": None, "broken": broken}


def run_gen(args, timeout=900):
    """Run a generator; return its key lines: FSR summary, settings and the saved file."""
    try:
        p = subprocess.run([PY, *args], cwd=HERE, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"error": "timed out"}
    text = p.stdout
    saved = re.findall(r"Saved (\S+\.txt)(.*)", text)
    fsr = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("FSR")]
    if not saved:
        tail = (p.stderr or text).strip().splitlines()[-1:] or ["no output"]
        return {"error": tail[0][:160]}
    path, extra = saved[-1]
    settings = re.search(r"window (\d+), k=([\d.]+)", extra)
    return {"file": os.path.relpath(path, HERE) if os.path.isabs(path) else path,
            "fsr": fsr[-1] if fsr else "", "settings": settings.group(0) if settings else "",
            "text": text}


# ---------------------------------------------------------------- virality -----------------
_wiki_cache = {}


def wiki_attention(query):
    """(article title, spike ratio): last 3 days of English Wikipedia views vs the median of the
    two months before. Above ~2x means people are actively looking it up right now."""
    if query in _wiki_cache:
        return _wiki_cache[query]
    result = (None, None)
    try:
        hits = requests.get("https://en.wikipedia.org/w/api.php", headers=UA, timeout=20, params={
            "action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json"}).json()
        title = hits["query"]["search"][0]["title"]
        end = date.today() - timedelta(1)
        start = end - timedelta(70)
        u = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
             f"{requests.utils.quote(title.replace(' ', '_'), safe='')}/daily/{start:%Y%m%d}/{end:%Y%m%d}")
        v = [i["views"] for i in requests.get(u, headers=UA, timeout=20).json().get("items", [])]
        if len(v) > 20:
            base = statistics.median(v[:-7]) or 1
            result = (title, sum(v[-3:]) / 3 / base)
        else:
            result = (title, None)
    except Exception:
        pass
    _wiki_cache[query] = result
    return result


def score_virality(items, rising_queries):
    """Fill item['viral'] = (wiki title, wiki ratio, matching YouTube rising searches)."""
    rising = [q.lower() for q in rising_queries]
    with ThreadPoolExecutor(8) as ex:
        attn = list(ex.map(lambda it: wiki_attention(it["query"]), items))
    for it, (title, ratio) in zip(items, attn):
        words = it["keywords"] or [w for w in it["title"].lower().split() if len(w) > 3]
        yt = [q for q in rising if any(w in q for w in words)]
        it["viral"] = (title, ratio, yt)
    return items


def viral_rank(it):
    _, ratio, yt = it["viral"] or (None, None, [])
    # cap: a brand-new article (tiny baseline) can show 1,000x+ and would always win
    return min(ratio or 0, 20) + (3 if yt else 0)


# ---------------------------------------------------------------- Earth / NASA -------------
def storms():
    """Hurricanes (64 kt+) and rapidly intensifying storms: the 6-hourly wind chart, saved."""
    active = requests.get("https://www.nhc.noaa.gov/CurrentStorms.json", headers=UA, timeout=30).json().get("activeStorms", [])
    out = []
    for st in sorted(active, key=lambda x: -int(x.get("intensity") or 0)):
        kt = int(st.get("intensity") or 0)
        p = subprocess.run([PY, "hurricane_gen.py", "--storm", st["id"]], cwd=HERE, capture_output=True, text=True,
                           timeout=300, encoding="utf-8", errors="replace")
        text = p.stdout
        ri = re.search(r"Biggest 24h gain: \+(\d+) kt \((\d+) -> (\d+)\) ending (\d{4}-\d\d-\d\d) (\d\d)Z", text)
        if ri:  # only count it if the burst ended in the last ~36 hours, not days ago
            ended = datetime.strptime(f"{ri.group(4)} {ri.group(5)}", "%Y-%m-%d %H").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - ended > timedelta(hours=36):
                ri = None
        if kt < 64 and not (ri and int(ri.group(1)) >= 30 and kt >= 34):
            continue  # hurricanes, or tropical storms that are rapidly intensifying right now
        lines = text.splitlines()
        wind = next((lines[i + 1] for i, ln in enumerate(lines) if ln.startswith("--- Wind") and i + 1 < len(lines)), "")
        if not wind.strip():
            continue
        path = os.path.join("output", f"{st['name'].lower()}_{st['id']}_wind_6hourly.txt")
        with open(os.path.join(HERE, path), "w") as f:
            f.write(wind.strip())
        cat = next((f"Cat {c}" for c, t in ((5, 137), (4, 113), (3, 96), (2, 83), (1, 64)) if kt >= t), st["classification"])
        why = f"{cat}, {kt} kt / {round(kt * 1.15078)} mph, {st['pressure']} mb" + (
            f", rapid intensification +{ri.group(1)} kt in 24h" if ri and int(ri.group(1)) >= 30 else "")
        out.append(item("storm", f"Hurricane {st['name']}" if kt >= 64 else f"Storm {st['name']}", why,
                        f"python hurricane_gen.py --storm {st['id']}",
                        {"file": path, "settings": "window 4, k=1", "fsr": ""},
                        query=f"Hurricane {st['name']} {datetime.now().year}", keywords=[st["name"]]))
    return out


def quakes():
    """M6+ in the last 72 hours: build the "every quake near the epicenter" chart."""
    feed = requests.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
                        headers=UA, timeout=60).json()["features"]
    now = datetime.now(timezone.utc).timestamp() * 1000
    big = [f for f in feed if (f["properties"]["mag"] or 0) >= 6.0 and now - f["properties"]["time"] < 3 * 86400000]
    out, done = [], []
    for f in sorted(big, key=lambda f: -f["properties"]["mag"]):
        lon, lat = f["geometry"]["coordinates"][:2]
        if any(abs(lat - a) < 3 and abs(lon - b) < 3 for a, b in done) or len(done) == 3:
            continue  # same sequence as a bigger quake already charted (~300 km)
        done.append((lat, lon))
        p = f["properties"]
        place = p["place"].split(", ")[-1] if ", " in p["place"] else p["place"]
        res = run_gen(["quake_gen.py", "--around", f"{lat:.3f}", f"{lon:.3f}"], timeout=300)
        res["settings"] = res.get("settings") or "window 12, k=1"
        when = datetime.fromtimestamp(p["time"] / 1000, timezone.utc)
        out.append(item("quake", f"M{p['mag']:.1f} earthquake, {p['place']}",
                        f"{when:%b %d %H:%M} UTC, depth {f['geometry']['coordinates'][2]:.0f} km"
                        + (f", alert {p['alert']}" if p.get("alert") else "") + (", tsunami flag" if p.get("tsunami") else ""),
                        f"python quake_gen.py --around {lat:.3f} {lon:.3f}", res,
                        query=f"{when.year} {place} earthquake", keywords=[place]))
    return out


FIRE_REGIONS = {"indonesia": "Indonesia", "california": "California", "amazon": "the Amazon",
                "canada": "Canada", "australia": "Australia", "borneo": "Borneo"}


def fires():
    """Fire seasons running far above normal, for every region with a FIRMS cache (the first
    download of a region takes ~35 min, so new regions are seeded by hand)."""
    out = []
    for slug, label in FIRE_REGIONS.items():
        if not os.path.exists(os.path.join(HERE, "output", "firms_cache", f"{slug}_MODIS.json")):
            continue
        res = run_gen(["fire_gen.py", "--preset", slug], timeout=1200)
        if "error" in res:
            log(f"  fires {slug}: {res['error']}")
            continue
        v = [int(x) for x in open(os.path.join(HERE, res["file"])).read().split(",")]
        months = []
        y, m = 2001, 1
        for _ in v:
            months.append((y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        last_full = len(v) - 2  # the newest month is partial
        same = sorted((v[i] for i in range(len(v) - 1) if months[i][1] == months[last_full][1]), reverse=True)
        rank = same.index(v[last_full]) + 1
        med = statistics.median(same) or 1
        if rank <= 3 and v[last_full] >= 2 * med:
            ym = f"{months[last_full][0]}-{months[last_full][1]:02d}"
            res["settings"] = res["settings"] or "window 12, k=1"
            out.append(item("fire", f"{label} fire season",
                            f"{ym}: {v[last_full]:,} satellite fire hotspots, #{rank} for that month since 2001 "
                            f"({v[last_full] / med:.1f}x the usual)",
                            f"python fire_gen.py --preset {slug}", res,
                            query=f"{datetime.now().year} {label} wildfires", keywords=[label.replace("the ", "")]))
    return out


def waves():
    """The biggest waves on Earth right now (NOAA buoys) - 6 m+ only."""
    lines = requests.get("https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt", headers=UA, timeout=60).text.splitlines()[2:]
    obs = []
    for ln in lines:
        f = ln.split()
        if len(f) > 11 and f[11] != "MM" and float(f[11]) >= 6.0:
            obs.append((float(f[11]), f[0], float(f[1]), float(f[2])))
    out = []
    for h, st, lat, lon in sorted(obs, reverse=True)[:2]:
        res = run_gen(["buoy_gen.py", st], timeout=300)
        out.append(item("waves", f"{h:.1f} m ({h * 3.281:.0f} ft) waves at buoy {st}",
                        f"{abs(lat):.0f}°{'N' if lat >= 0 else 'S'} {abs(lon):.0f}°{'E' if lon >= 0 else 'W'}, biggest on the NOAA network now",
                        f"python buoy_gen.py {st}", res, query=f"buoy {st} storm", keywords=[st]))
    return out


STATES = {"AL": "Alabama", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "FL": "Florida",
          "GA": "Georgia", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
          "LA": "Louisiana", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
          "NE": "Nebraska", "NV": "Nevada", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
          "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "SC": "South Carolina",
          "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia", "WA": "Washington",
          "WI": "Wisconsin", "WY": "Wyoming"}


def drought():
    """States where drought spread fastest over the last 4 weekly maps (+20 points or more)."""
    from drought_gen import FIPS
    start = (date.today() - timedelta(45)).strftime("%m/%d/%Y")

    def one(st):
        r = requests.get("https://usdmdataservices.unl.edu/api/StateStatistics/GetDroughtSeverityStatisticsByAreaPercent",
                         headers={"Accept": "text/csv"}, timeout=60, params={
                             "aoi": FIPS[st], "startdate": start, "enddate": date.today().strftime("%m/%d/%Y"),
                             "statisticsType": "1"})
        rows = sorted(r.text.splitlines()[1:])
        d1 = [float(x.split(",")[4]) for x in rows if x.count(",") > 5]
        return st, (d1[-1] - d1[-5]) if len(d1) >= 5 else None, d1[-1] if d1 else None

    with ThreadPoolExecutor(8) as ex:
        res = [r for r in ex.map(one, STATES) if r[1] is not None]
    out = []
    for st, jump, now in sorted(res, key=lambda r: -r[1])[:2]:
        if jump < 20:
            continue
        g = run_gen(["drought_gen.py", "--state", st, "--since", "2020", "--metric", "d1"], timeout=300)
        broken = "WARNING" in g.get("text", "")
        warn = " (zero-drought weeks break this chart - caption fact, not a chart)" if broken else ""
        g["settings"] = g["settings"] or "window 12, k=1"
        out.append(item("drought", f"{STATES[st]} drought spreading",
                        f"{now:.0f}% of {STATES[st]} in drought, +{jump:.0f} points in 4 weeks{warn}",
                        f"python drought_gen.py --state {st} --since 2020 --metric d1", g,
                        query=f"{STATES[st]} drought", keywords=[STATES[st]], broken=broken))
    return out


def flu():
    res = run_gen(["flu_gen.py"], timeout=180)
    m = re.search(r"Rising (\d+) weeks in a row", res.get("text", ""))
    if not m or int(m.group(1)) < 4:
        return []
    latest = re.search(r"latest ([\d.]+)%", res["text"])
    res["settings"] = res["settings"] or "window 8, k=1"
    return [item("flu", "Flu season climbing", f"rising {m.group(1)} weeks in a row, {latest.group(1) if latest else '?'}% of doctor visits",
                 "python flu_gen.py", res, query="influenza", keywords=["flu season", "influenza"])]


def tornadoes():
    """30+ preliminary tornado reports in the last 7 days."""
    from tornado_gen import daily_reports
    days = [date.today() - timedelta(n) for n in range(1, 8)]
    with ThreadPoolExecutor(7) as ex:
        reps = list(ex.map(daily_reports, days))
    total = sum(len(r) for _, r in reps)
    if total < 30:
        return []
    states = sorted({r["State"] for _, rows in reps for r in rows})
    res = run_gen(["tornado_gen.py"], timeout=600)
    res["settings"] = res["settings"] or "window 12, k=1"
    return [item("tornado", "Tornado outbreak", f"{total} tornado reports in 7 days ({' '.join(states[:10])})",
                 "python tornado_gen.py", res, query="tornado outbreak", keywords=["tornado"])]


def groundwater():
    """Saved NASA groundwater regions sitting at a record low (no download - reads the files)."""
    import glob
    out = []
    for path in glob.glob(os.path.join(HERE, "output", "groundwater_*.txt")):
        v = [float(x) for x in open(path).read().split(",") if x.strip()]
        if len(v) > 60 and v[-1] <= min(v) * 1.003:
            slug = os.path.basename(path)[12:-4]
            out.append(item("groundwater", f"Groundwater record low: {slug.replace('_', ' ')}",
                            f"{v[-1]:.0f} mm, lowest in {len(v) // 12} years of NASA data",
                            f"python groundwater_gen.py --preset {slug}",
                            {"file": os.path.relpath(path, HERE), "settings": "window 6, k=1", "fsr": ""},
                            query=f"{slug.replace('_', ' ')} groundwater", keywords=[slug.replace("_", " ")]))
    return out


# ---------------------------------------------------------------- sports -------------------
def mlb():
    """Every starter tonight and tomorrow (postseason first): each one's most-thrown pitch,
    every pitch of the season. Capped at 6 pitchers to keep the digest's run time sane."""
    pitchers = []
    for d in (date.today(), date.today() + timedelta(1)):
        js = requests.get("https://statsapi.mlb.com/api/v1/schedule", timeout=30, params={
            "sportId": 1, "date": d.isoformat(), "hydrate": "probablePitcher"}).json()
        for day in js.get("dates", []):
            for g in day["games"]:
                post = g.get("gameType") in ("F", "D", "L", "W")
                for side, other in (("away", "home"), ("home", "away")):
                    pp = g["teams"][side].get("probablePitcher")
                    if pp:
                        pitchers.append((not post, d, pp["fullName"], g["teams"][side]["team"]["name"],
                                         g["teams"][other]["team"]["name"], g.get("seriesDescription", "")))
    out = []
    for _, d, name, team, opp, series in sorted(pitchers)[:6]:
        res = run_gen(["pitch_velo_gen.py", name], timeout=900)
        avg = re.search(r"Average ([\d.]+) mph", res.get("text", ""))
        head = re.search(r": (\d+) (\w+) pitches over (\d+) games", res.get("text", ""))
        why = (f"{'tonight' if d == date.today() else 'tomorrow'} {series or 'vs'} vs {opp}"
               + (f" - {head.group(1)} {head.group(2)} this season, avg {avg.group(1)} mph" if head and avg else ""))
        out.append(item("mlb", f"{name} ({team})", why, f'python pitch_velo_gen.py "{name}"', res,
                        query=name, keywords=[name.split()[-1]]))
    return out


ESPN_TO_NBA = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS"}


def _nba_top_scorers():
    """Team abbreviation -> last season's leading scorer (points per game, 40+ games)."""
    from nba_api.stats.endpoints import leaguedashplayerstats  # (LeagueLeaders returns HTML now)
    from nba_data_gen import HEADERS, current_season_start, season_label
    season = season_label(current_season_start() - 1)
    df = leaguedashplayerstats.LeagueDashPlayerStats(season=season, per_mode_detailed="PerGame",
                                                     headers=HEADERS, timeout=60).get_data_frames()[0]
    df = df[df.GP >= 40].sort_values("PTS", ascending=False).drop_duplicates("TEAM_ABBREVIATION")
    return {r.TEAM_ABBREVIATION: (r.PLAYER_NAME, float(r.PTS)) for r in df.itertuples()}


def nba():
    """Tonight's NBA games: the leading scorer on each side, game by game (top 4 by scoring)."""
    js = requests.get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                      headers=UA, timeout=30, params={"dates": date.today().strftime("%Y%m%d")}).json()
    # skip preseason games (stars barely play); each game carries its own season type -
    # the league-level one describes TODAY, not the date asked for
    games = [e for e in js.get("events", []) if (e.get("season") or {}).get("type") != 1]
    if not games:
        return []
    top = _nba_top_scorers()
    stars = []
    for e in games:
        comp = e["competitions"][0]["competitors"]
        names = " vs ".join(c["team"]["displayName"] for c in comp)
        for c in comp:
            abbr = ESPN_TO_NBA.get(c["team"]["abbreviation"], c["team"]["abbreviation"])
            if abbr in top:
                stars.append((-top[abbr][1], top[abbr][0], top[abbr][1], names))
    out = []
    for _, name, ppg, matchup in sorted(stars)[:4]:
        res = run_gen(["nba_data_gen.py", name, "PTS"], timeout=600)
        out.append(item("nba", name, f"tonight {matchup} - {ppg:.1f} ppg last season",
                        f'python nba_data_gen.py "{name}" PTS', res, query=name, keywords=[name.split()[-1]]))
    return out


def nfl():
    """NFL primetime games this week (no NFL generator yet - listed for the hook)."""
    js = requests.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", headers=UA, timeout=30).json()
    out = []
    for e in js.get("events", []):
        when = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        local_hour = (when - timedelta(hours=6)).hour  # Mountain time, near enough for "primetime"
        if e["status"]["type"]["state"] == "pre" and local_hour >= 17:
            out.append(item("nfl", e["name"], f"{when - timedelta(hours=6):%a %b %d %I:%M %p} MT (primetime)",
                            "", query=e["name"].split(" at ")[-1], keywords=[w for w in e["name"].split() if len(w) > 4]))
    return out


EARTH_SCANS = [storms, quakes, fires, waves, drought, flu, tornadoes, groundwater]
SPORTS_SCANS = [mlb, nba, nfl]


def run_scans(scans):
    items = []
    for scan in scans:
        log(f"  -> live scan: {scan.__name__}")
        try:
            items += scan()
        except Exception as e:
            log(f"  {scan.__name__} failed: {type(e).__name__}: {e}")
    return items


def fmt(it):
    """One Markdown bullet for an item."""
    out = it["out"]
    parts = [f"- **{it['title']}** - {it['why']}"]
    if out.get("file"):
        parts.append(f"  - file `{out['file']}`" + (f" ({out['settings']})" if out.get("settings") else ""))
        if out.get("fsr"):
            parts.append(f"  - {out['fsr'][:150]}")
    elif out.get("error"):
        parts.append(f"  - generator failed: {out['error']}")
    if it["cmd"]:
        parts.append(f"  - rerun: `{it['cmd']}`")
    if it["viral"]:
        title, ratio, yt = it["viral"]
        tags = []
        if ratio:
            shown = f"{ratio:.1f}x" if ratio < 50 else "50x+ (new article)"
            tags.append(f"Wikipedia {shown} normal" + (f" ({title})" if title else ""))
        if yt:
            tags.append("YouTube rising: " + ", ".join(yt[:3]))
        if tags:
            parts.append("  - " + " | ".join(tags))
    return parts
