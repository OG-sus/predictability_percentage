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
"""
import argparse
import time
import warnings

warnings.filterwarnings("ignore")

DEFAULT_SEEDS = ["price", "prices", "crash", "collapse", "record", "economy", "stock", "game", "shortage"]
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


def main():
    parser = argparse.ArgumentParser(description="YouTube search demand via Google Trends")
    parser.add_argument("--rising", nargs="*", help="show rising searches for these seeds (default seeds if none)")
    parser.add_argument("--interest", nargs="+", help="relative YouTube search interest for these terms")
    args = parser.parse_args()
    if args.interest:
        for t, v in sorted(interest(args.interest).items(), key=lambda x: -x[1]):
            print(f"  {t:<30} {v:>6.2f}x '{ANCHOR}'")
    if args.rising is not None or not args.interest:
        for seed, qs in rising(args.rising or DEFAULT_SEEDS).items():
            print(f"\n'{seed}': " + " | ".join(f"{q} ({v})" for q, v in qs))


if __name__ == "__main__":
    main()
