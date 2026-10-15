"""
morning_digest.py - one report of what moved overnight, for picking the day's Shorts

Runs the engine-first sources in one pass and writes a Markdown digest to
output/digest/YYYY-MM-DD_am.md or _pm.md (also printed). Every section is independent:
if one source is down, the rest still run.

  1. Engine picks   - scanner_gen: biggest recent stability cracks (wiki/FRED/markets/anime)
  2. Storms         - NHC active storms, major hurricanes, rapid intensification
  3. Markets        - 1-day / 5-day moves, new 52-week highs & lows
  4. Fresh FRED     - watched economic series updated in the last 3 days
  5. Netflix Top 10 - this week's #1s, biggest new entries, longest runner
  6. Robotaxis      - Texas fleet counts vs a week ago
  7. Anime          - AniList top trending
  8. AI status      - OpenAI/Anthropic incidents; appends to output/ai_incidents.jsonl
  9. Economy pulse  - TSA travel, jobless claims, gas, mortgage, 10-yr, sentiment, eggs, beef (add to PULSE_FRED)
 10. Chart finder   - long FRED + science series ranked by how much the engine shows (data first)
 11. YouTube rising - fastest-rising US YouTube searches (Google Trends) to match against data
 12. Earth & NASA   - live scans that RUN the generators: big quakes, fire seasons, giant waves,
                      drought spreading, flu, tornadoes, groundwater lows (digest_live.py)
 13. Sports         - tonight's/tomorrow's MLB starters and NBA stars, charts built; NFL primetime
  0. Ready to chart - everything from 12-13 ranked by how viral it is right now (Wikipedia spike +
                      YouTube rising), printed at the TOP of the digest

Run:
    python morning_digest.py
    python morning_digest.py --quick     # skip the slow full scan (wiki/anime), ~1 min
    python morning_digest.py --no-live   # skip sections 12-13 (they run generators, ~10-20 min)

Scheduled at 7am and 5pm via Windows Task Scheduler - see register_digest_task.ps1.
"""
import argparse
import csv
import io
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output", "digest")

MARKET_WATCH = {
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^VIX": "VIX", "DX-Y.NYB": "Dollar index",
    "GC=F": "Gold", "SI=F": "Silver", "CL=F": "Crude oil", "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum",
    "NVDA": "Nvidia", "MU": "Micron", "AMD": "AMD", "INTC": "Intel", "ORCL": "Oracle", "BE": "Bloom Energy",
    "TSLA": "Tesla", "SONY": "Sony", "MSFT": "Microsoft", "AAPL": "Apple", "WBD": "Warner Bros", "PSKY": "Paramount",
}
FRED_WATCH = ["DGS10", "MORTGAGE30US", "CPIAUCSL", "UNRATE", "PAYEMS", "REVOLSL", "ASPUS", "MSACSR",
              "HOUST", "UMCSENT", "GASREGW", "DCOILWTICO", "PCU334112334112", "DRCCLACBS",
              "TLMFGCONS", "TTLCONS", "DHHNGSP", "APU0000708111"]
NETFLIX_TSV = "https://www.netflix.com/tudum/top10/data/all-weeks-global.tsv"


def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


RISING_QUERIES = []  # filled by youtube_rising(), used to score the live items' virality
SEEN_PATH = os.path.join(OUT_DIR, "seen.json")
SEEN_DAYS = 7     # an item shown in full comes back in full only after this many days


def _load_seen():
    import json
    try:
        with open(SEEN_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


SEEN = _load_seen()


def split_fresh(kind, items, key):
    """(fresh, repeats): fresh = not shown in full in the last SEEN_DAYS days."""
    shown = SEEN.setdefault(kind, {})
    cutoff = (datetime.now() - timedelta(days=SEEN_DAYS)).isoformat()
    fresh, repeats = [], []
    for it in items:
        (repeats if shown.get(key(it), "") > cutoff else fresh).append(it)
    return fresh, repeats


def mark_shown(kind, items, key):
    SEEN.setdefault(kind, {}).update({key(it): datetime.now().isoformat() for it in items})


def save_seen():
    import json
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(SEEN, f, indent=1)


def section(title):
    """Decorator: run a section, and on any failure record the error instead of crashing."""
    def wrap(fn):
        def run(*a, **kw):
            log(f"-> {title}")
            start = time.time()
            try:
                lines = fn(*a, **kw) or ["_nothing notable_"]
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                lines = [f"_section failed: {type(e).__name__}: {e}_"]
            return [f"## {title}", *lines, f"<sub>{time.time() - start:.0f}s</sub>", ""]
        return run
    return wrap


@section("1. Engine picks - biggest stability cracks")
def engine_picks(quick):
    from scanner_gen import scan
    results = scan(["fred", "market"] if quick else None)
    lines = ["Scans the fixed watchlists PLUS today's top Wikipedia articles and freshly updated FRED series.",
             "**full arc** = spiked and already settled (rise, peak, fall) - the chart shape that works best.", "",
             "| # | source | series | normal | low | crack | cracked on | status |", "|---|---|---|---|---|---|---|---|"]
    results, repeats = split_fresh("engine", results, lambda r: r["series"])
    mark_shown("engine", results[:15], lambda r: r["series"])
    for i, r in enumerate(results[:15], 1):
        if r["latest"] >= r["normal"] - 10:
            status = f"**full arc** (back to {r['latest']:.0f}%)"
        elif r["latest"] <= r["now"] + 1:
            status = "still spiking"
        else:
            status = f"recovering ({r['latest']:.0f}%)"
        lines.append(f"| {i} | {r['source']} | {r['series'][:50]} | {r['normal']:.0f}% | {r['now']:.0f}% | "
                     f"+{r['crack']:.0f} | {r['crack_date']} | {status} |")
    lines.append("")
    arcs = [r for r in results if r["latest"] >= r["normal"] - 10][:3]
    lines += [f"- full arc: `{r['command']}`" for r in arcs]
    if repeats:
        lines.append(f"\n_Shown in the last {SEEN_DAYS} days, still cracking:_ " + ", ".join(r["series"][:40] for r in repeats[:15]))
    return lines


@section("2. Storms (NHC)")
def storms():
    from hurricane_gen import active_storms, storm_track
    lines = []
    for s in active_storms():
        kt = int(s["intensity"])
        cat = next((c for c, t in ((5, 137), (4, 113), (3, 96), (2, 83), (1, 64)) if kt >= t), None)
        label = f"Cat {cat}" if cat else s["classification"]
        note = ""
        try:
            _, times, pts = storm_track(s["id"])
            wind = [pts[t][0] for t in times]
            if len(wind) > 4 and wind[-1] - wind[-5] >= 30:
                note = f" - **rapid intensification: +{wind[-1] - wind[-5]} kt in 24h**"
        except Exception:
            pass
        flag = "**MAJOR** " if cat and cat >= 3 else ""
        lines.append(f"- {flag}{s['name']} ({label}, {kt} kt / {round(kt * 1.15078)} mph, {s['pressure']} mb){note}"
                     f" - `python hurricane_gen.py --storm {s['id']}`")
    return lines


@section("3. Markets")
def markets():
    import yfinance as yf
    rows = []
    for sym, name in MARKET_WATCH.items():
        try:
            h = yf.Ticker(sym).history(period="1y")["Close"].dropna()
            v = [float(x) for x in h]
            if len(v) < 6:
                continue
            d1, d5 = (v[-1] / v[-2] - 1) * 100, (v[-1] / v[-6] - 1) * 100
            tag = "**52-wk HIGH**" if v[-1] >= max(v) else "**52-wk LOW**" if v[-1] <= min(v) else ""
            rows.append((abs(d1), f"| {name} | {v[-1]:,.2f} | {d1:+.1f}% | {d5:+.1f}% | {tag} |"))
        except Exception as e:
            log(f"  skip {sym}: {e}")
    rows.sort(reverse=True)
    return ["| asset | last | 1 day | 5 days | |", "|---|---|---|---|---|"] + [r for _, r in rows]


@section("4. Fresh FRED releases (last 3 days)")
def fresh_fred():
    from FRED_gen import fetch_series, fred
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    lines = []
    for sid in FRED_WATCH:
        try:
            info = fred("series", series_id=sid)["seriess"][0]
            updated = datetime.strptime(info["last_updated"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if updated < cutoff:
                continue
            _, d, v = fetch_series(sid, since=str(datetime.now().year - 3))
            chg = f"{(v[-1] / v[-2] - 1) * 100:+.1f}% vs prior" if len(v) > 1 and v[-2] else ""
            hi = " - **3-yr high**" if v[-1] >= max(v) else " - **3-yr low**" if v[-1] <= min(v) else ""
            lines.append(f"- **{sid}** {info['title'][:60]}: {v[-1]:,} ({d[-1]}) {chg}{hi} - "
                         f"`python FRED_gen.py {sid} --since 2006`")
        except Exception as e:
            log(f"  skip {sid}: {e}")
    return lines


@section("5. Netflix Top 10 (global, latest week)")
def netflix():
    text = requests.get(NETFLIX_TSV, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    week = max(r["week"] for r in rows)
    cur = [r for r in rows if r["week"] == week]
    title = lambda r: r["season_title"] if r["season_title"] != "N/A" else r["show_title"]
    views = lambda r: float(r["weekly_views"] or 0) / 1e6
    lines = [f"Week of {week}:"]
    lines += [f"- #1 {r['category']}: **{title(r)}** - {views(r):.1f}M views (week {r['cumulative_weeks_in_top_10']})"
              for r in cur if r["weekly_rank"] == "1"]
    new = sorted((r for r in cur if r["cumulative_weeks_in_top_10"] == "1"), key=views, reverse=True)[:3]
    if new:
        lines.append("- New this week: " + ", ".join(f"{title(r)} ({views(r):.1f}M)" for r in new))
    longest = max(cur, key=lambda r: int(r["cumulative_weeks_in_top_10"] or 0))
    lines.append(f"- Longest running: {title(longest)} - week {longest['cumulative_weeks_in_top_10']}")
    return lines


@section("6. Texas robotaxis")
def robotaxis():
    from texas_av_gen import BRANDS, daily_series, fetch
    today = datetime.now(timezone.utc).date()
    lines = []
    for b in BRANDS:
        data = fetch(b)
        _, s = daily_series(data["history"], today)
        week = s[-8] if len(s) >= 8 else s[0]
        added = len(data.get("addedToday") or [])
        lines.append(f"- {b.title()}: {s[-1]:,} registered ({s[-1] - week:+,} vs a week ago)"
                     + (f" - **{added} added today**" if added else ""))
    return lines


@section("7. Anime - AniList trending")
def anime():
    from anilist_gen import TOP_QUERY, gql, show_title
    shows = gql(TOP_QUERY)["Page"]["media"][:5]
    return [f"- {show_title(m)} (trending {m['trending']}, {m['popularity']:,} on lists, {m['status'].lower()})"
            for m in shows]


# Economy pulse: fast, felt signals. Add a FRED series ID + label here to follow more.
PULSE_FRED = {
    "ICSA": "Weekly jobless claims",
    "GASREGW": "Gas, regular ($/gal)",
    "MORTGAGE30US": "30-yr mortgage rate (%)",
    "DGS10": "10-yr Treasury yield (%)",
    "UMCSENT": "Consumer sentiment",
    "APU0000708111": "Eggs ($/dozen)",
    "APU0000703112": "Ground beef ($/lb)",
}


@section("9. Economy pulse")
def economy_pulse():
    from FRED_gen import fetch_series
    lines = ["| signal | latest | vs prior | vs 1 yr ago | |", "|---|---|---|---|---|"]
    try:
        from tsa_gen import fetch_daily
        daily = fetch_daily(date_today().year - 1)
        last = max(daily)
        now28 = sum(daily.get(last - timedelta(days=i), 0) for i in range(28))
        ago28 = sum(daily.get(last - timedelta(days=364 + i), 0) for i in range(28))
        lines.append(f"| TSA travelers (28-day) | {daily[last]:,} ({last:%b %d}) | | {(now28 / ago28 - 1) * 100:+.1f}% | |")
    except Exception as e:
        log(f"  skip TSA: {e}")
    for sid, label in PULSE_FRED.items():
        try:
            _, d, v = fetch_series(sid, since=str(datetime.now().year - 5))
            prev = v[-2]
            yr_i = next((i for i in range(len(d) - 1, -1, -1) if d[i] <= f"{int(d[-1][:4]) - 1}{d[-1][4:]}"), None)
            yoy = f"{(v[-1] / v[yr_i] - 1) * 100:+.1f}%" if yr_i is not None else ""
            tag = "**5-yr HIGH**" if v[-1] >= max(v) else "**5-yr LOW**" if v[-1] <= min(v) else ""
            lines.append(f"| {label} | {v[-1]:,g} ({d[-1]}) | {(v[-1] / prev - 1) * 100:+.1f}% | {yoy} | {tag} |")
        except Exception as e:
            log(f"  skip {sid}: {e}")
    return lines


@section("10. Chart finder - long series with the most for the engine to show")
def chart_finder():
    """Data first: ranks long FRED + science series by calculator-worthiness (several real
    cracks, long history, something current). Kaggle is skipped here to keep the run short -
    run `python chart_finder_gen.py` for the full scan."""
    import json
    from chart_finder_gen import OUT, diversify, safe_name, scan_fred, scan_science
    results = diversify(sorted([r for r in scan_science() if r] + [r for r in scan_fred(150) if r],
                               key=lambda r: -r["score"]))
    results, repeats = split_fresh("chartfinder", results, lambda r: r["name"].split(" - ")[0])
    mark_shown("chartfinder", results[:12], lambda r: r["name"].split(" - ")[0])
    os.makedirs(OUT, exist_ok=True)
    lines = ["| # | series | points | normal | low | now | shape |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results[:12], 1):
        with open(os.path.join(OUT, safe_name(r["name"]) + ".txt"), "w") as f:
            f.write(", ".join(f"{v:g}" for v in r["_values"]))
        lines.append(f"| {i} | {r['name'][:60]} | {r['points']} | {r['normal']:.0f}% | {r['lowest']:.0f}% | "
                     f"{r['latest']:.0f}% | {r['shape']}{' - record level' if r['at_extreme'] else ''} |")
    lines.append(f"\nSeries files: output/chartfinder/<name>.txt (window = points/25). Cracks for #1: "
                 f"{', '.join(results[0]['crack_dates'])}" if results else "_no new series this run_")
    if repeats:
        lines.append(f"\n_Already shown this week:_ " + ", ".join(r["name"].split(" - ")[0] for r in repeats[:15]))
    return lines


@section("11. YouTube rising searches - what people want to watch")
def youtube_rising():
    """Audience first: the fastest-rising US YouTube searches for broad seed words.
    Match these against real data (generators / chart finder) - most are news with no
    series behind them, a few point straight at a long dataset."""
    from yt_demand_gen import match, rising
    found = rising()
    RISING_QUERIES.extend(q for qs in found.values() for q, _ in qs if not q.startswith("(failed"))
    matched, unmatched, seen = [], [], set()
    for seed, qs in found.items():
        for q, v in qs:
            if q in seen or q.startswith("(failed"):
                continue
            seen.add(q)
            hit = match(q)
            (matched if hit else unmatched).append((v, q, hit))
    matched, repeats = split_fresh("rising", sorted(matched, reverse=True), lambda m: m[1])
    mark_shown("rising", matched, lambda m: m[1])
    lines = ["**NEW rising searches WITH long data behind them (ready to run):**"]
    lines += [f"- **{q}** (rise {v}) → {hit}" for v, q, hit in matched] or ["- _nothing new today_"]
    if repeats:
        lines.append(f"\n_Still rising (shown before):_ " + ", ".join(q for _, q, _ in repeats))
    lines.append(f"\nNo chartable data (news): " + ", ".join(q for _, q, _ in sorted(unmatched, reverse=True)[:25]))
    return lines


def date_today():
    return datetime.now().date()


AI_STATUS_PAGES = {
    "OpenAI": "https://status.openai.com/api/v2/incidents.json",
    "Anthropic": "https://status.anthropic.com/api/v2/incidents.json",
}
AI_INCIDENT_LOG = os.path.join(HERE, "output", "ai_incidents.jsonl")


@section("8. AI service status (incident log)")
def ai_status():
    """Status pages only expose their last ~25-50 incidents, so every run appends any
    new ones to output/ai_incidents.jsonl - that file becomes the long-run time series."""
    import json
    known = set()
    if os.path.exists(AI_INCIDENT_LOG):
        with open(AI_INCIDENT_LOG, encoding="utf-8") as f:
            known = {json.loads(line)["id"] for line in f if line.strip()}
    now = datetime.now(timezone.utc)
    lines, added = [], 0
    with open(AI_INCIDENT_LOG, "a", encoding="utf-8") as log_file:
        for company, url in AI_STATUS_PAGES.items():
            incidents = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).json()["incidents"]
            for inc in incidents:
                if inc["id"] not in known:
                    log_file.write(json.dumps({"id": inc["id"], "company": company, "created_at": inc["created_at"],
                                               "resolved_at": inc.get("resolved_at"), "impact": inc.get("impact"),
                                               "name": inc["name"]}) + "\n")
                    known.add(inc["id"])
                    added += 1
            created = [datetime.fromisoformat(i["created_at"].replace("Z", "+00:00")) for i in incidents]
            last_day = sum(1 for t in created if now - t <= timedelta(days=1))
            last_week = sum(1 for t in created if now - t <= timedelta(days=7))
            ongoing = [i["name"] for i in incidents if not i.get("resolved_at")]
            lines.append(f"- {company}: {last_day} incident(s) in 24h, {last_week} in 7 days"
                         + (f" - **ongoing: {'; '.join(n[:60] for n in ongoing)}**" if ongoing else ""))
    lines.append(f"- Logged {added} new incident(s) to output/ai_incidents.jsonl")
    return lines


def live_sections():
    """Sections 12-13 plus the 'Ready to chart' summary. Returns (section lines, summary lines)."""
    import digest_live as L
    sections, every = [], []
    for title, scans in (("12. Earth & NASA - live (charts already built)", L.EARTH_SCANS),
                         ("13. Sports - tonight & tomorrow (charts already built)", L.SPORTS_SCANS)):
        log(f"-> {title}")
        start = time.time()
        items = L.run_scans(scans)
        L.score_virality(items, RISING_QUERIES)
        every += items
        lines = [ln for it in sorted(items, key=L.viral_rank, reverse=True) for ln in L.fmt(it)] or ["_nothing notable_"]
        sections += [f"## {title}", *lines, f"<sub>{time.time() - start:.0f}s</sub>", ""]
    ready = [it for it in sorted(every, key=L.viral_rank, reverse=True)
             if it["out"].get("file") and not it["broken"]][:8]
    summary = ["## 0. Ready to chart - most viral first",
               "Series files already saved; settings in brackets. Wikipedia = attention vs the last two months.", ""]
    for i, it in enumerate(ready, 1):
        _, ratio, yt = it["viral"] or (None, None, [])
        heat = (f"Wikipedia {ratio:.1f}x" if ratio else "") + (" + YouTube rising" if yt else "")
        summary.append(f"{i}. **{it['title']}** - {it['why']}" + (f" - {heat}" if heat else ""))
        summary.append(f"   `{it['out']['file']}` ({it['out'].get('settings') or 'see section'})")
    return sections, (summary + [""] if ready else [])


def main():
    parser = argparse.ArgumentParser(description="Morning digest of what moved overnight")
    parser.add_argument("--quick", action="store_true", help="skip the slow Wikipedia/anime scan")
    parser.add_argument("--no-live", action="store_true", help="skip the live generator scans (sections 12-13)")
    args = parser.parse_args()

    os.chdir(HERE)  # generators expect to run from the project folder (.env, fsr.py)
    now = datetime.now()
    parts = [f"# Morning digest - {now:%A %B %d, %Y  %I:%M %p}", ""]
    parts += engine_picks(args.quick)
    parts += storms()
    parts += markets()
    parts += fresh_fred()
    parts += netflix()
    parts += robotaxis()
    parts += anime()
    parts += ai_status()
    parts += economy_pulse()
    parts += chart_finder()
    parts += youtube_rising()
    ready = []
    if not args.no_live:
        live, ready = live_sections()
        parts += live
    save_seen()
    parts[2:2] = ready  # "Ready to chart" goes right under the title

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{now:%Y-%m-%d}_{'am' if now.hour < 12 else 'pm'}.md")  # 7am + 5pm runs
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("\n".join(parts))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
