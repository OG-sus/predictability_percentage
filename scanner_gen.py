"""
scanner_gen.py - let the FSR engine pick the topic

Runs a sliding-window Predictability Score across a basket of real series
(Wikipedia attention, FRED economics, stocks/crypto, airing anime) and
ranks them by how hard their stability cracked recently compared with
their own normal. The engine finds the story; the news explains it after.

For each series:
  normal = median sliding-window score over its history (minus the recent stretch)
  now    = lowest sliding-window score in the recent stretch
  crack  = normal - now   (bigger = stability broke harder)

Reuses the fetchers from FRED_gen / pageviews_gen / anilist_gen, and
yfinance for markets, so nothing new to install.

Run:
    python scanner_gen.py                        # scan everything, show top 10
    python scanner_gen.py --top 20
    python scanner_gen.py --only wiki fred       # just some sources (wiki, fred, market, anime)
    python scanner_gen.py --add-wiki "Hollow Knight: Silksong" "Clair Obscur: Expedition 33"
    python scanner_gen.py --csv                  # also save scan_results.csv
"""
import argparse
import csv
import statistics
import sys
import time

from fsr import calculate_predictability

# ---- The basket. Add freely - anything that fails to fetch is skipped. ----
WIKI_ARTICLES = [
    # gaming / tech hardware (the channel's best-performing lane)
    "PlayStation 5", "Nintendo Switch 2", "Xbox Series X and Series S", "Steam Deck",
    "GeForce RTX 50 series", "Nvidia", "Graphics processing unit", "DDR5 SDRAM",
    "Solid-state drive", "Grand Theft Auto VI", "Minecraft", "Fortnite", "Roblox",
    "Hideo Kojima", "Pokémon", "Valve Corporation",
    # AI / tech
    "ChatGPT", "Artificial intelligence", "OpenAI",
    # money / economy
    "Recession", "Stagflation", "Inflation", "Tariff", "Credit card", "Lipstick effect",
    "Bitcoin", "Gold as an investment",
]
FRED_SERIES = [
    "REVOLSL", "TERMCBCCALLNS", "DGS10", "MORTGAGE30US", "GASREGW", "GASDESW",
    "CPIAUCSL", "UNRATE", "DCOILWTICO", "UMCSENT",
]
MARKET_TICKERS = ["NVDA", "MU", "AMD", "INTC", "SONY", "NTDOY", "MSFT", "AAPL", "TSLA", "BTC-USD", "ETH-USD"]
ANIME_TOP_N = 5

# window size / recent stretch (both in data points) per data frequency
FREQ_SETTINGS = {
    "D": (7, 14),    # daily: 1-week window, look at the last 2 weeks
    "W": (8, 4),     # weekly: 2-month window, last month
    "M": (12, 3),    # monthly: 1-year window, last quarter
    "Q": (8, 2),     # quarterly: 2-year window, last half-year
}
MARKET_SETTINGS = (20, 10)  # trading days: ~1-month window, last 2 weeks


def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def rolling_scores(values, window, k):
    return [calculate_predictability(values[i - window:i], k) for i in range(window, len(values) + 1)]


def assess(source, label, dates, values, window, recent, k, command):
    """Score one series. Returns None if there isn't enough history to judge."""
    if len(values) < window + recent * 3:
        return None
    r = rolling_scores(values, window, k)
    history, tail = r[:-recent], r[-recent:]
    normal = statistics.median(history)
    now = min(tail)
    # rolling score i covers values[i : i+window], so it ends on dates[i + window - 1]
    crack_i = len(r) - recent + tail.index(now)
    return {
        "source": source, "series": label, "normal": normal, "now": now, "latest": r[-1],
        "crack": normal - now, "crack_date": dates[crack_i + window - 1],
        "last_date": dates[-1], "command": command,
    }


# ---- Sources -----------------------------------------------------------------
def scan_wiki(articles):
    from pageviews_gen import fetch_views
    window, recent = FREQ_SETTINGS["D"]
    for term in articles:
        try:
            title, dates, views = fetch_views(term, 365, weekly=False)
            yield assess("wiki", title, dates, views, window, recent, 1.0,
                         f'python pageviews_gen.py "{title}" --days 365')
        except Exception as e:
            log(f"  skip wiki '{term}': {e}")
        time.sleep(0.2)  # be polite to Wikimedia


def scan_fred(series_ids):
    from FRED_gen import fetch_series
    since = {"D": None, "W": "2016", "M": "2006", "Q": "1995"}
    for sid in series_ids:
        try:
            info, dates, values = fetch_series(sid, since="2016")
            freq = info["frequency_short"]
            if freq in since and since[freq] != "2016":
                info, dates, values = fetch_series(sid, since=since[freq])
            if freq == "D":
                dates, values = dates[-500:], values[-500:]
            window, recent = FREQ_SETTINGS.get(freq, FREQ_SETTINGS["M"])
            yield assess("fred", f"{sid} - {info['title'][:60]}", dates, values, window, recent, 2.0,
                         f"python FRED_gen.py {sid} --since {dates[0][:4]} --window {window}")
        except Exception as e:
            log(f"  skip fred {sid}: {e}")


def scan_market(tickers):
    import yfinance as yf
    window, recent = MARKET_SETTINGS
    for sym in tickers:
        try:
            hist = yf.Ticker(sym).history(period="1y")["Close"].dropna()
            dates = [d.strftime("%Y-%m-%d") for d in hist.index]
            yield assess("market", sym, dates, [float(v) for v in hist], window, recent, 2.0,
                         f"python stock_fsr_chart.py {sym}")
        except Exception as e:
            log(f"  skip market {sym}: {e}")


def scan_anime(top_n):
    from datetime import datetime, timezone
    from anilist_gen import TOP_QUERY, fetch_trends, gql, show_title
    window, recent = FREQ_SETTINGS["D"]
    try:
        shows = gql(TOP_QUERY)["Page"]["media"][:top_n]
    except Exception as e:
        log(f"  skip anime: {e}")
        return
    for m in shows:
        name = m["title"]["romaji"]
        try:
            media, nodes = fetch_trends(name, 120)
            pts = [n for n in nodes if n["inProgress"] is not None]
            dates = [datetime.fromtimestamp(n["date"], tz=timezone.utc).strftime("%Y-%m-%d") for n in pts]
            yield assess("anime", show_title(media), dates, [n["inProgress"] for n in pts], window, recent, 1.0,
                         f'python anilist_gen.py "{name}" --days 120')
        except Exception as e:
            log(f"  skip anime '{name}': {e}")


def scan(sources=None, extra_wiki=()):
    """Run the scan and return every result, biggest crack first (used by morning_digest.py)."""
    sources = set(sources or ["wiki", "fred", "market", "anime"])
    scanners = []
    if "wiki" in sources:
        scanners.append(("Wikipedia", scan_wiki(WIKI_ARTICLES + list(extra_wiki))))
    if "fred" in sources:
        scanners.append(("FRED", scan_fred(FRED_SERIES)))
    if "market" in sources:
        scanners.append(("markets", scan_market(MARKET_TICKERS)))
    if "anime" in sources:
        scanners.append(("AniList", scan_anime(ANIME_TOP_N)))
    results = []
    for name, gen in scanners:
        log(f"Scanning {name}...")
        results.extend(r for r in gen if r)
    return sorted(results, key=lambda r: r["crack"], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Rank real series by how hard their stability cracked recently")
    parser.add_argument("--top", type=int, default=10, help="how many results to show (default 10)")
    parser.add_argument("--only", nargs="+", choices=["wiki", "fred", "market", "anime"],
                        help="scan only these sources")
    parser.add_argument("--add-wiki", nargs="+", default=[], metavar="ARTICLE",
                        help="extra Wikipedia articles to include this run")
    parser.add_argument("--csv", action="store_true", help="also save every result to scan_results.csv")
    args = parser.parse_args()

    results = scan(args.only, args.add_wiki)
    if not results:
        print("Nothing scanned successfully - check your internet connection / API keys.")
        return

    print(f"\nScanned {len(results)} series. Biggest recent stability cracks:\n")
    print(f"{'#':>2}  {'source':<7} {'series':<46} {'normal':>6} {'now':>6} {'crack':>6}  cracked on")
    for i, r in enumerate(results[:args.top], 1):
        print(f"{i:>2}  {r['source']:<7} {r['series'][:46]:<46} {r['normal']:>5.1f}% {r['now']:>5.1f}% "
              f"{r['crack']:>+5.1f}  {r['crack_date']}  (latest {r['latest']:.1f}%)")
    print("\nDig into one with:")
    for i, r in enumerate(results[:min(args.top, 5)], 1):
        print(f"  {i}. {r['command']}")

    if args.csv:
        with open("scan_results.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print("\nSaved scan_results.csv")


if __name__ == "__main__":
    main()
