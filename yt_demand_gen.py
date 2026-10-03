"""
yt_demand_gen.py - what are people searching on YouTube? (Google Trends, YouTube Search mode)

Two jobs:
  1. rising(seeds)  - the fastest-RISING YouTube searches containing broad seed words
                      ("price", "crash", "record"...) - an audience-first idea list to
                      match against real time-series data.
  2. interest(terms)- relative YouTube search interest for specific topics, all scaled
                      against one anchor term so batches compare fairly.

Note: Google Trends is unofficial and rate-limited; calls are spaced out and retried.
Search demand matters most for long-form (people find it by searching); Shorts mostly
travel through the swipe feed, so treat interest as a tie-breaker, not a verdict.

Run:
    python yt_demand_gen.py --rising                       # default seeds
    python yt_demand_gen.py --rising price collapse record
    python yt_demand_gen.py --interest "gas prices" "housing market" "egg prices"
    python yt_demand_gen.py --match "justin verlander last game" "iphone 18 price"
"""
import argparse
import re
import time
import warnings

warnings.filterwarnings("ignore")

# Broad on purpose: the FSR engine applies to ANY time series that needs stability.
DEFAULT_SEEDS = [
    # money / markets
    "price", "prices", "crash", "collapse", "record", "economy", "stock", "shortage",
    # sports
    "nfl", "nba", "mlb", "playoffs",
    # tech / AI / gaming
    "ai", "outage", "steam", "ps5",
    # engineering / sensors / infrastructure / energy
    "failure", "earthquake", "hurricane", "oil well", "drilling", "power grid",
    # health / pharma
    "drug", "recall", "fda",
]
ANCHOR = "gas prices"


def _client():
    from pytrends.request import TrendReq
    return TrendReq(hl="en-US", tz=360, timeout=(10, 30))


def _call(fn, tries=3, wait=20):
    for attempt in range(tries):
        try:
            return fn()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(wait)


def rising(seeds=DEFAULT_SEEDS, per_seed=8, timeframe="today 1-m"):
    """{seed: [(query, rise_score), ...]} of rising US YouTube searches."""
    py, out = _client(), {}
    for seed in seeds:
        try:
            def go():
                py.build_payload([seed], timeframe=timeframe, geo="US", gprop="youtube")
                return py.related_queries()[seed]["rising"]
            rq = _call(go)
            out[seed] = [] if rq is None else [(q, int(v)) for q, v in rq.head(per_seed).values]
        except Exception as e:
            out[seed] = [("(failed: " + type(e).__name__ + ")", 0)]
        time.sleep(8)
    return out


def interest(terms, timeframe="today 3-m"):
    """{term: interest relative to ANCHOR (1.0 = as searched as 'gas prices')}."""
    py, raw = _client(), {}
    for i in range(0, len(terms), 4):
        batch = terms[i:i + 4]
        def go():
            py.build_payload([ANCHOR] + batch, timeframe=timeframe, geo="US", gprop="youtube")
            return py.interest_over_time()
        df = _call(go)
        base = df[ANCHOR].mean() or 1
        for t in batch:
            raw[t] = round(df[t].mean() / base, 2)
        time.sleep(8)
    return raw


# ── Matching: rising search -> real long data that exists for it ─────────────
NOISE = re.compile(r"\b(last game|highlights?|news|today|live|stats?|reaction|video|full|explained|"
                   r"update|2026|2025|review|prediction|trailer|interview|retire(s|d|ment)?)\b", re.I)


def _clean(q):
    return re.sub(r"\s+", " ", NOISE.sub(" ", q)).strip()


def _mlb(q):
    import requests
    name = _clean(q)
    if len(name.split()) < 2:
        return None
    people = requests.get("https://statsapi.mlb.com/api/v1/people/search", params={"names": name},
                          timeout=15).json().get("people", [])
    p = next((p for p in people if p["fullName"].lower() in q.lower()), None)
    if not p:
        return None
    if p.get("primaryPosition", {}).get("abbreviation") == "P":
        return f"MLB pitcher career data - `python mlb_pitcher_gen.py \"{p['fullName']}\" --career`"
    return f"MLB player {p['fullName']} (hitter - career data via MLB Stats API; pitcher tool doesn't cover hitters yet)"


_NETFLIX = None


def _netflix(q):
    global _NETFLIX
    import csv as _csv, io, requests
    if _NETFLIX is None:
        text = requests.get("https://www.netflix.com/tudum/top10/data/all-weeks-global.tsv",
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
        rows = list(_csv.DictReader(io.StringIO(text), delimiter="\t"))
        _NETFLIX = {}
        for r in rows:
            _NETFLIX.setdefault(r["show_title"].lower(), set()).add(r["week"])
    words = [w for w in re.findall(r"[a-z0-9]+", _clean(q).lower()) if w not in ("the", "a", "of")]
    hit = next((t for t in _NETFLIX
                if len(words) >= 2 and all(w in re.findall(r"[a-z0-9]+", t) for w in words)), None)
    return f"Netflix Top 10: '{hit}' - {len(_NETFLIX[hit])} weeks of views/hours" if hit else None


def _price(q):
    m = re.match(r"\s*(.+?)\s+prices?\s*$", _clean(q), re.I)      # only "<item> price(s)"
    if not m or m.group(1).lower().startswith(("the ", "a ")):     # not "the price is right"
        return None
    item = m.group(1).strip().lower()
    from FRED_gen import fred
    found = fred("series/search", search_text=f"{item} price", order_by="popularity", sort_order="desc",
                 limit=20).get("seriess", [])
    tokens = re.findall(r"[a-z]+", item)
    s = next((s for s in found if s["observation_start"] <= "2016-01-01"
              and all(t in s["title"].lower() for t in tokens)), None)   # title must name the item
    return (f"FRED price series {s['id']} ({s['title'][:50]}, since {s['observation_start'][:4]}) - "
            f"`python FRED_gen.py {s['id']} --since 2006`") if s else None


QUAKE_NOISE = re.compile(r"\b(sim|simulator|sounds?|movie|scene|game|the last day|drill|prank|snl|wkuk|"
                         r"song|meme|asmr)\b", re.I)


def _real_place(place):
    """True only if the words name an actual place (geocoder agrees), not a meme/person/show."""
    import requests
    place = re.sub(r"\bstate\b", "", place, flags=re.I).strip()
    if len(place) < 4 or not place.replace(" ", "").isalpha():
        return False
    r = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": place, "count": 1},
                     timeout=20).json().get("results")
    if not r:
        return False
    names = {str(r[0].get(k, "")).lower() for k in ("name", "admin1", "country")}
    return place.lower() in names


def _quake(q):
    m = re.search(r"(.*?)\s*earthquakes?\s*(?:in\s+)?(.*)", q, re.I)
    if not m or QUAKE_NOISE.search(q):
        return None
    place = _clean(m.group(1) or m.group(2) or "").strip(" -,")   # "earthquake today" -> worldwide
    if not place:
        return "USGS earthquake counts - `python quake_gen.py --world --minmag 5 --years 20`"
    if not _real_place(place):
        return None
    return f"USGS earthquake counts near {place} - `python quake_gen.py --place \"{place}\"`"


NOT_A_RECALL = re.compile(r"total recall|active recall|mass recall|don'?t recall|recall saying|recall study", re.I)


def _fda_months(search, kind="drug", events=False):
    """Months of real openFDA data for this term (0 if none) - so the digest never points at empty data."""
    from fda_gen import monthly_counts
    try:
        m = monthly_counts(kind, events, search)
    except BaseException:          # monthly_counts exits on "no results"
        return 0
    vals = sorted(m.values())
    return len(vals) if vals and vals[len(vals) // 2] >= 3 else 0   # median >= 3/month or it's noise


def _fda(q):
    """Only product-specific recall / adverse-event searches that have years of real FDA data.
    'fda commissioner', 'fda nominee' etc. are news - no series measures them."""
    if NOT_A_RECALL.search(q):
        return None
    m = re.search(r"(.*?)\s*\b(recall(?:s|ed)?|adverse events?|side effects?)\b", q, re.I)
    if not m:
        return None
    item = re.sub(r"\b(on|fda|the)\b", " ", _clean(m.group(1)), flags=re.I).strip()
    if not item:
        return None
    if m.group(2).lower().startswith(("adverse", "side")):
        n = _fda_months(item, events=True)
        return f"FDA adverse-event reports for {item} ({n} months) - `python fda_gen.py --events --search \"{item}\"`" if n >= 60 else None
    for kind in ("drug", "food", "device"):
        n = _fda_months(item, kind)
        if n >= 60:
            return f"FDA {kind} recalls mentioning {item} ({n} months) - `python fda_gen.py --kind {kind} --search \"{item}\"`"
    return None


ENERGY = re.compile(r"\b(oil|gas|natural gas|crude|drilling|rig|well|power grid|electricity|coal|refinery)\b", re.I)


def _eia(q):
    """Energy searches FRED can't serve well -> EIA presets (needs EIA_API_KEY)."""
    t = q.lower()
    grids = {"texas": "ERCO", "ercot": "ERCO", "california": "CISO", "pjm": "PJM", "new york": "NYIS", "miso": "MISO"}
    region = next((code for name, code in grids.items() if name in t), None)
    # a named US grid, or US-wide demand - not Cuba/Puerto Rico, board games, video games or "threat" news
    if (region and re.search(r"grid|electricity|power|blackout", t)) or re.search(r"(us|u\.s\.|america\w*) (power )?grid demand|electricity demand", t):
        region = region or "US48"
        return f"EIA daily grid demand ({region}) - `python eia_gen.py --preset grid --region {region} --since 2022`"
    if re.search(r"(us|u\.s\.|american?|texas|shale)? ?(crude )?oil (production|output)|crude production|barrels per day", t):
        return "EIA U.S. crude oil production - `python eia_gen.py --preset crude --since 2000`"
    if "gas storage" in t or "natural gas storage" in t:
        return "EIA natural gas storage - `python eia_gen.py --preset gas_storage`"
    return None


def _energy(q):
    """Energy/drilling searches -> a matching long FRED series (title must contain the words)."""
    if not ENERGY.search(q):
        return None
    from FRED_gen import fred
    words = [w for w in re.findall(r"[a-z]+", _clean(q).lower()) if w not in ("the", "us", "in", "of", "and")]
    found = fred("series/search", search_text=" ".join(words), order_by="popularity", sort_order="desc",
                 limit=20).get("seriess", [])
    ok = [s for s in found if s["observation_start"] <= "2016-01-01" and all(w in s["title"].lower() for w in words)]
    us = [s for s in ok if re.search(r"united states|\bu\.s\.|\bus\b", s["title"], re.I)]   # prefer US series
    s = (us or ok or [None])[0]
    return (f"FRED energy series {s['id']} ({s['title'][:50]}, since {s['observation_start'][:4]}) - "
            f"`python FRED_gen.py {s['id']} --since 2006`") if s else None


def _wiki(q):
    from pageviews_gen import resolve_title
    try:
        title = resolve_title(_clean(q))
        return f"Wikipedia attention since 2015 - `python pageviews_gen.py \"{title}\" --days 3650 --weekly`"
    except Exception:
        return None


def match(query):
    """First real long-data source that fits this search, or None (news with nothing to chart)."""
    for fn in (_mlb, _quake, _fda, _eia, _netflix, _price, _energy, _wiki):
        try:
            hit = fn(query)
            if hit:
                return hit
        except Exception:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description="YouTube search demand via Google Trends")
    parser.add_argument("--rising", nargs="*", help="show rising searches for these seeds (default seeds if none)")
    parser.add_argument("--interest", nargs="+", help="relative YouTube search interest for these terms")
    parser.add_argument("--match", nargs="+", help="find the real long data behind these search phrases")
    args = parser.parse_args()
    if args.match:
        for q in args.match:
            print(f"  {q:<40} -> {match(q) or 'no long data found (news)'}")
        return
    if args.interest:
        for t, v in sorted(interest(args.interest).items(), key=lambda x: -x[1]):
            print(f"  {t:<30} {v:>6.2f}x '{ANCHOR}'")
    if args.rising is not None or not args.interest:
        for seed, qs in rising(args.rising or DEFAULT_SEEDS).items():
            print(f"\n'{seed}': " + " | ".join(f"{q} ({v})" for q, v in qs))


if __name__ == "__main__":
    main()
