"""
FRED_gen.py - Predictability Score for any FRED economic series

Pulls any series from the St. Louis Fed's FRED database (free, uses
FRED_API_KEY from .env - same key the ticker feed uses) and scores it.
Plain requests against the FRED REST API, so no fredapi install needed.

Run:
    python FRED_gen.py REVOLSL --since 2006              # US credit card debt, 20 years
    python FRED_gen.py DGS10 --since 2006 --window 100   # 10-year Treasury + sliding window lows
    python FRED_gen.py GASDESW --last 500 --csv          # last 500 points of diesel, save CSV
    python FRED_gen.py --search "credit card"            # find series IDs by keyword

Handy IDs:
    REVOLSL        credit card / revolving debt ($ millions, monthly)
    TERMCBCCALLNS  credit card interest rate (%)
    DRCCLACBS      credit card delinquency rate (%, quarterly)
    DGS10          10-year Treasury yield (%, daily)
    MORTGAGE30US   30-year mortgage rate (%, weekly)
    CPIAUCSL       CPI / inflation index (monthly)
    UNRATE         unemployment rate (%, monthly)
    GASDESW        diesel price ($/gal, weekly)
"""
import argparse
import csv
import os

import requests
from dotenv import load_dotenv

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

BASE = "https://api.stlouisfed.org/fred"


def fred(endpoint: str, **params) -> dict:
    load_dotenv()
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY not set. Add it to your .env file.")
    resp = requests.get(f"{BASE}/{endpoint}", timeout=20,
                        params={"api_key": api_key, "file_type": "json", **params})
    if resp.status_code == 400:
        raise ValueError(resp.json().get("error_message", "Bad FRED request - check the series ID."))
    resp.raise_for_status()
    return resp.json()


def fetch_series(series_id: str, since: str = None):
    info = fred("series", series_id=series_id)["seriess"][0]
    params = {"series_id": series_id}
    if since:
        # accept 2006, 2006-08, or 2006-08-15 - FRED itself only takes the full date
        params["observation_start"] = (since + "-01-01")[:10] if len(since) == 4 else (since + "-01")[:10]
    # FRED marks missing observations (holidays, etc.) as "." - skip them.
    obs = [o for o in fred("series/observations", **params)["observations"] if o["value"] != "."]
    if not obs:
        raise ValueError(f"No observations for {series_id} in that range.")
    return info, [o["date"] for o in obs], [float(o["value"]) for o in obs]


def search(term: str):
    results = fred("series/search", search_text=term, order_by="popularity", limit=15)["seriess"]
    print(f"\nTop FRED series for '{term}':\n")
    for s in results:
        print(f"{s['id']:<16} {s['title'][:70]}  [{s['frequency_short']}, {s['units_short']}, "
              f"{s['observation_start'][:4]}-{s['observation_end'][:4]}]")


def main():
    parser = argparse.ArgumentParser(description="FSR predictability score for any FRED economic series")
    parser.add_argument("series", nargs="?", help="FRED series ID, e.g. REVOLSL, DGS10, UNRATE")
    parser.add_argument("--search", metavar="TERM", help="look up series IDs by keyword instead")
    parser.add_argument("--since", help="start year or date, e.g. 2006 or 2019-06-01 (default: full history)")
    parser.add_argument("--last", type=int, help="keep only the most recent N points")
    parser.add_argument("--window", type=int, help="also run a sliding window of this size and show its lowest points")
    parser.add_argument("--k", type=float, default=2.0,
                        help="k-factor: 2.0=finance (default, the standard for economic data), 1.0=general")
    parser.add_argument("--csv", action="store_true", help="also save the series as <id>_fred.csv")
    args = parser.parse_args()

    if args.search:
        search(args.search)
        return
    if not args.series:
        parser.error("give a FRED series ID, or use --search")

    info, dates, values = fetch_series(args.series.upper(), args.since)
    if args.last:
        dates, values = dates[-args.last:], values[-args.last:]
    score = calculate_predictability(values, args.k)

    hi = values.index(max(values))
    lo = values.index(min(values))
    print(f"\n{info['id']}: {info['title']}")
    print(f"{info['frequency']}, {info['units']}  (last updated {info['last_updated'][:10]})")
    print(f"Range: {dates[0]} to {dates[-1]}, {len(values)} points")
    print(f"Latest: {values[-1]:,}  |  High: {values[hi]:,} on {dates[hi]}  |  Low: {values[lo]:,} on {dates[lo]}")
    print(f"\nPredictability Score (k={args.k}): {score:.1f}%")

    if args.window:
        sw = calculate_sliding_window(values, args.window, k=args.k)
        if sw:
            # window_end is 1-based, so the window's last date is dates[window_end - 1]
            lows = sorted(sw, key=lambda r: r["score"])[:3]
            print(f"Sliding window ({args.window}): latest {sw[-1]['score']:.1f}%, lowest " +
                  ", ".join(f"{r['score']:.1f}% (ending {dates[r['window_end'] - 1]})" for r in lows))
        else:
            print(f"Sliding window ({args.window}) is bigger than the series ({len(values)} points).")

    print("\n--- Series (copy for a chart) ---")
    print(", ".join(f"{v:g}" for v in values))

    if args.csv:
        path = f"{info['id'].lower()}_fred.csv"
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", info["id"]])
            writer.writerows(zip(dates, values))
        print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
