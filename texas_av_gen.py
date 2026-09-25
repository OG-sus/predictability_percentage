"""
texas_av_gen.py - Predictability Score for Texas robotaxi fleets

Daily fleet size for every autonomous-vehicle operator registered with the
Texas DMV (Tesla, Waymo, Zoox, Avride), via texasavtracker.com's public
JSON feed (it snapshots the TxDMV Automated Vehicle Registry). Its history
only records days the count changed, so this forward-fills to one point per
day. Registry tracking starts 2026-05-28.

Run:
    python texas_av_gen.py                    # all operators, scores + daily series
    python texas_av_gen.py tesla              # one operator (tesla, waymo, zoox, avride)
    python texas_av_gen.py tesla --models     # also break the fleet down by model (Model Y vs Cybercab)
    python texas_av_gen.py --csv              # save texas_av_fleet.csv (one column per operator)

Data credit: texasavtracker.com (source: TxDMV Automated Vehicle Registry).
"""
import argparse
import csv
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import requests

from fsr import calculate_predictability

API = "https://texasavtracker.com/api/data?brand={brand}"
BRANDS = ["tesla", "waymo", "zoox", "avride"]
HEADERS = {"User-Agent": "predictability-api.com FSR script (predictabilitycalculator@gmail.com)"}


def fetch(brand: str) -> dict:
    resp = requests.get(API.format(brand=brand), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def daily_series(history: list, end: date):
    """Forward-fill the change-point history into one count per calendar day."""
    pts = sorted((date.fromisoformat(h["timestamp"][:10]), h["count"]) for h in history)
    days = [pts[0][0] + timedelta(i) for i in range((end - pts[0][0]).days + 1)]
    series, cur, j = [], None, 0
    for d in days:
        while j < len(pts) and pts[j][0] <= d:
            cur = pts[j][1]  # several snapshots on one day -> keep the last
            j += 1
        series.append(cur)
    return [d.isoformat() for d in days], series


def model_breakdown(data: dict):
    """When each model showed up, from the per-VIN first-seen dates."""
    model_of = {v["vin"]: v["model"] for v in data["vehicles"]}
    first_seen = Counter()
    earliest = {}
    for vin, seen in data.get("vinDates", {}).items():
        model = model_of.get(vin)
        if model:
            first_seen[model] += 1
            earliest[model] = min(earliest.get(model, seen), seen)
    return {m: (first_seen[m], earliest[m][:10]) for m in first_seen}


def main():
    parser = argparse.ArgumentParser(description="FSR predictability score for Texas robotaxi fleet sizes")
    parser.add_argument("brand", nargs="?", choices=BRANDS, help="one operator (default: all)")
    parser.add_argument("--models", action="store_true", help="show fleet by vehicle model")
    parser.add_argument("--k", type=float, default=2.0,
                        help="k-factor: 2.0=finance (default), 1.0=general")
    parser.add_argument("--csv", action="store_true", help="save texas_av_fleet.csv")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).date()
    brands = [args.brand] if args.brand else BRANDS
    columns = {}
    for b in brands:
        data = fetch(b)
        dates, series = daily_series(data["history"], today)
        columns[b] = dict(zip(dates, series))
        score = calculate_predictability(series, args.k)
        biggest = max(range(1, len(series)), key=lambda i: series[i] - series[i - 1])
        print(f"\n{data['operatorInfo']['companyName']}  ({len(data['vehicles'])} vehicles registered now)")
        print(f"  {dates[0]}: {series[0]:,}  ->  {dates[-1]}: {series[-1]:,}  "
              f"(x{series[-1] / series[0]:.1f}, +{series[-1] - series[0]:,})")
        print(f"  Biggest one-day jump: +{series[biggest] - series[biggest - 1]:,} on {dates[biggest]}")
        print(f"  Predictability Score (k={args.k}): {score:.1f}%")
        if data.get("addedToday"):
            print(f"  Added today: {len(data['addedToday'])}")
        if args.models:
            for model, (n, first) in sorted(model_breakdown(data).items(), key=lambda x: -x[1][0]):
                print(f"    {model:<12} {n:>5} vehicles, first registered {first}")
        print("  --- Series (copy for a chart) ---")
        print("  " + ", ".join(map(str, series)))

    if args.csv:
        all_dates = sorted({d for col in columns.values() for d in col})
        with open("texas_av_fleet.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date"] + brands)
            for d in all_dates:
                writer.writerow([d] + [columns[b].get(d, "") for b in brands])
        print("\nSaved texas_av_fleet.csv")


if __name__ == "__main__":
    main()
