"""
flu_gen.py - FSR on CDC flu activity (ILINet, weekly since Oct 1997, free, no key)

The number is % of doctor visits for flu-like illness (weighted ILI), via CMU Delphi's mirror
of CDC FluView. It never touches zero (summer floor ~0.4%), and every winter is a full
rise-peak-fall, so it charts cleanly. Season peaks: 2009 pandemic 7.7, 2017-18 7.5,
2025-26 8.3 (highest in the data).

Run:
    python flu_gen.py                      # national, every week since 1997
    python flu_gen.py --since 2015         # shorter
    python flu_gen.py --region hhs6        # an HHS region (hhs1..hhs10), or a state: --region tx
"""
import argparse
import os
import statistics
from datetime import date

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
DELPHI = "https://api.delphi.cmu.edu/epidata/fluview/"


def fetch(region, since):
    r = requests.get(DELPHI, timeout=90, params={
        "regions": region, "epiweeks": f"{max(since, 1997)}01-{date.today().year}53"}).json()
    rows = [(e["epiweek"], e["wili"] if e.get("wili") is not None else e.get("ili"))
            for e in r.get("epidata") or []]
    rows = [(w, v) for w, v in sorted(rows) if v is not None]
    if not rows:
        raise SystemExit(f"No flu data for region '{region}': {r.get('message')}")
    return [(f"{w // 100}-wk{w % 100:02d}", v) for w, v in rows]


def main():
    p = argparse.ArgumentParser(description="FSR on CDC flu activity (ILINet)")
    p.add_argument("--region", default="nat", help="nat, hhs1..hhs10, or a state like tx (default nat)")
    p.add_argument("--since", type=int, default=1997)
    p.add_argument("--window", type=int, default=8, help="weeks (default 8)")
    p.add_argument("--k", type=float, default=1.0)
    a = p.parse_args()

    rows = fetch(a.region.lower(), a.since)
    weeks, v = [w for w, _ in rows], [x for _, x in rows]
    hi = v.index(max(v))
    print(f"\nFlu-like illness, {a.region}: {len(v)} weeks, {weeks[0]} to {weeks[-1]} (% of doctor visits)")
    print(f"Typical {statistics.median(v):.2f}% | record {v[hi]:.2f}% ({weeks[hi]}) | latest {v[-1]:.2f}% "
          f"| 4 weeks ago {v[-5]:.2f}% | 1 year ago {v[-53]:.2f}%")
    rising = 0
    while rising + 1 < len(v) and v[-1 - rising] > v[-2 - rising]:
        rising += 1
    if rising >= 3:
        print(f"Rising {rising} weeks in a row.")
    r = [calculate_predictability(v[i - a.window:i], a.k) for i in range(a.window, len(v) + 1)]
    e = weeks[a.window - 1:]
    print(f"FSR (k={a.k}) overall {calculate_predictability(v, a.k):.2f}% | {a.window}-week window: typical "
          f"{statistics.median(r):.1f}%, lowest {min(r):.1f}% ({e[r.index(min(r))]}), latest {r[-1]:.1f}%")
    path = os.path.join(HERE, "output", f"flu_{a.region.lower()}_since{a.since}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{x:.3f}" for x in v))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
