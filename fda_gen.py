"""
fda_gen.py - FSR on FDA safety data over time (openFDA, free, no key)

Counts per month of:
  recalls          - drug / device / food enforcement reports (since ~2004-2012)
  adverse events   - drug adverse-event reports (FAERS, since ~2004)
optionally narrowed to one product or term. Fed straight into the FSR engine.

Watch for: FAERS counts jump when manufacturers file reports in bulk - a spike can be
paperwork, not patients. Say "reports", not "cases".

Run:
    python fda_gen.py                                   # all drug recalls per month
    python fda_gen.py --kind device                     # device recalls (also: food)
    python fda_gen.py --events --search semaglutide     # adverse-event reports for one drug
    python fda_gen.py --kind drug --search insulin --window 12
"""
import argparse
import os
import statistics
from collections import OrderedDict

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://api.fda.gov"


def monthly_counts(kind="drug", events=False, search=None):
    """{YYYY-MM: count} from openFDA's per-day counts."""
    if events:
        url, field = f"{BASE}/drug/event.json", "receivedate"
        # space = OR in openFDA syntax (a literal "+" gets URL-encoded and breaks the query)
        q = (f'patient.drug.openfda.generic_name:"{search}" patient.drug.openfda.brand_name:"{search}"'
             if search else None)
    else:
        url, field = f"{BASE}/{kind}/enforcement.json", "report_date"
        q = f'"{search}"' if search else None
    params = {"count": field}
    if q:
        params["search"] = q
    resp = requests.get(url, params=params, timeout=60)
    body = resp.json()
    if "results" not in body:
        raise SystemExit(f"openFDA: {body.get('error', {}).get('message', 'no results')}")
    months = OrderedDict()
    for row in sorted(body["results"], key=lambda r: r["time"]):
        key = f"{row['time'][:4]}-{row['time'][4:6]}"
        months[key] = months.get(key, 0) + row["count"]
    return months


def main():
    parser = argparse.ArgumentParser(description="FSR on FDA recall / adverse-event counts")
    parser.add_argument("--kind", choices=["drug", "device", "food"], default="drug", help="recall type")
    parser.add_argument("--events", action="store_true", help="drug adverse-event reports instead of recalls")
    parser.add_argument("--search", help="narrow to a product or term, e.g. insulin, semaglutide")
    parser.add_argument("--window", type=int, default=12, help="sliding window in months (default 12)")
    parser.add_argument("--k", type=float, default=1.0)
    args = parser.parse_args()

    m = monthly_counts(args.kind, args.events, args.search)
    months, v = list(m), list(m.values())
    what = ("adverse-event reports" if args.events else f"{args.kind} recalls") + (f" - '{args.search}'" if args.search else "")
    print(f"\nFDA {what}: {len(v)} months, {months[0]} to {months[-1]}")
    hi = v.index(max(v))
    print(f"Latest {v[-1]:,} ({months[-1]}, may be partial) | peak {v[hi]:,} ({months[hi]}) | median {statistics.median(v):,.0f}")
    print(f"FSR (k={args.k}): {calculate_predictability(v, args.k):.1f}%")
    if len(v) > args.window:
        r = [calculate_predictability(v[i - args.window:i], args.k) for i in range(args.window, len(v) + 1)]
        lows = sorted(range(len(r)), key=r.__getitem__)[:3]
        print(f"{args.window}-month window: typical {statistics.median(r):.1f}%, latest {r[-1]:.1f}%, lowest "
              + ", ".join(f"{r[i]:.1f}% (ending {months[i + args.window - 1]})" for i in lows))
    slug = ("events" if args.events else args.kind + "_recalls") + (f"_{args.search.lower().replace(' ', '_')}" if args.search else "")
    path = os.path.join(HERE, "output", f"fda_{slug}_monthly.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(map(str, v)))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
