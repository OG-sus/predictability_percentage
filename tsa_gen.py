"""
tsa_gen.py - Predictability Score for US air travel (TSA checkpoint counts)

TSA publishes how many people pass through airport security every day
(tsa.gov/travel/passenger-volumes, 2019-present, updated daily). Economists
watch it as a real-time spending signal - drops in air travel came before
the 2001 and 2008 recessions. Daily numbers swing hard by weekday, so the
default is weekly totals (Mon-Sun), which is what the engine should read.

Run:
    python tsa_gen.py                        # weekly totals since 2023, year-over-year check
    python tsa_gen.py --since 2019           # full history incl. the 2020 collapse
    python tsa_gen.py --daily --since 2026   # raw daily counts
    python tsa_gen.py --window 8 --csv       # sliding window + save tsa_weekly.csv
"""
import argparse
import csv
import re
from datetime import date, datetime, timedelta

import requests

from fsr import calculate_predictability

BASE = "https://www.tsa.gov/travel/passenger-volumes"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128"}
ROW = re.compile(r'<td[^>]*>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>\s*<td[^>]*>\s*([\d,]+)\s*</td>')


def fetch_daily(since_year):
    """{date: travelers} for every day from since_year through yesterday."""
    counts = {}
    this_year = date.today().year
    for year in range(since_year, this_year + 1):
        url = BASE if year == this_year else f"{BASE}/{year}"
        html = requests.get(url, headers=HEADERS, timeout=30).text
        for d, n in ROW.findall(html):
            counts[datetime.strptime(d, "%m/%d/%Y").date()] = int(n.replace(",", ""))
    if not counts:
        raise SystemExit("No TSA data parsed - the page layout may have changed.")
    return dict(sorted(counts.items()))


def weekly_totals(daily):
    """Sum complete Mon-Sun weeks only, so a partial current week doesn't look like a collapse."""
    weeks = {}
    for d, n in daily.items():
        monday = d - timedelta(days=d.weekday())
        weeks.setdefault(monday, []).append(n)
    return {m: sum(v) for m, v in weeks.items() if len(v) == 7}


def main():
    parser = argparse.ArgumentParser(description="FSR predictability score for TSA checkpoint travel counts")
    parser.add_argument("--since", type=int, default=2023, help="first year (TSA data starts 2019)")
    parser.add_argument("--daily", action="store_true", help="use raw daily counts instead of weekly totals")
    parser.add_argument("--window", type=int, default=8, help="sliding window size (default 8 weeks)")
    parser.add_argument("--k", type=float, default=1.0, help="k-factor (1.0 general)")
    parser.add_argument("--csv", action="store_true", help="save tsa_daily.csv / tsa_weekly.csv")
    args = parser.parse_args()

    daily = fetch_daily(max(2019, args.since))
    days = list(daily)
    last = days[-1]

    # Year-over-year on the same weekdays: compare the last 28 days to the 28 days 364 days earlier.
    recent = [daily[last - timedelta(days=i)] for i in range(28) if last - timedelta(days=i) in daily]
    prior = [daily[last - timedelta(days=364 + i)] for i in range(28) if last - timedelta(days=364 + i) in daily]
    busiest = max(daily, key=daily.get)

    print(f"\nTSA checkpoint travelers: {days[0]} to {last} ({len(daily)} days)")
    print(f"Latest day: {daily[last]:,} ({last:%a %b %d})   Busiest day on record: {daily[busiest]:,} ({busiest})")
    if len(recent) == 28 and len(prior) == 28:
        print(f"Last 28 days vs same weekdays a year ago: {sum(recent):,} vs {sum(prior):,} "
              f"({(sum(recent) / sum(prior) - 1) * 100:+.1f}%)")

    if args.daily:
        labels, series, unit = [str(d) for d in days], list(daily.values()), "daily"
    else:
        weeks = weekly_totals(daily)
        labels, series, unit = [f"week of {m}" for m in weeks], list(weeks.values()), "weekly"

    score = calculate_predictability(series, args.k)
    print(f"\n{len(series)} {unit} points | Predictability Score (k={args.k}): {score:.1f}%")
    if len(series) > args.window:
        roll = [calculate_predictability(series[i - args.window:i], args.k) for i in range(args.window, len(series) + 1)]
        lows = sorted(range(len(roll)), key=roll.__getitem__)[:3]
        print(f"Sliding window ({args.window}): latest {roll[-1]:.1f}%, lowest " +
              ", ".join(f"{roll[i]:.1f}% ({labels[i + args.window - 1]})" for i in lows))

    print(f"\n--- {unit.title()} travelers (copy for a chart) ---")
    print(", ".join(map(str, series)))

    if args.csv:
        path = f"tsa_{unit}.csv"
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["period", "travelers"])
            writer.writerows(zip(labels, series))
        print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
