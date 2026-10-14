"""
drought_gen.py - FSR on the U.S. Drought Monitor (weekly since 2000, free, no key)

Each Tuesday's map gives the share of an area in each drought level (D0 abnormally dry ...
D4 exceptional). Two ways to chart it:
  --metric dsci  Drought Severity & Coverage Index (0-500): every level weighted together.
                 Smoothest series and the default.
  --metric d1    % of the area in drought (D1 or worse) - the number news reports quote.

Wet states sit at 0% for months, and FSR breaks near zero, so a state chart usually needs a
later --since (Texas: 2020 on). The lower 48 never gets near zero.

Run:
    python drought_gen.py                          # lower 48, DSCI, since 2000
    python drought_gen.py --metric d1              # lower 48, % in drought
    python drought_gen.py --state TX --since 2020  # Texas
"""
import argparse
import csv
import io
import os
import statistics
from datetime import date

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://usdmdataservices.unl.edu/api"
FIPS = {"AL": "01", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "FL": "12",
        "GA": "13", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22",
        "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
        "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
        "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47",
        "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56"}


def fetch(state, metric, since):
    scope = "StateStatistics" if state else "USStatistics"
    aoi = FIPS[state] if state else "us"  # the state endpoint wants FIPS codes, not "TX"
    call = "GetDSCI" if metric == "dsci" else "GetDroughtSeverityStatisticsByAreaPercent"
    r = requests.get(f"{API}/{scope}/{call}", headers={"Accept": "text/csv"}, timeout=90, params={
        "aoi": aoi, "startdate": f"1/1/{since}", "enddate": f"{date.today():%m/%d/%Y}", "statisticsType": "1"})
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    if not state and rows and "AreaOfInterest" in rows[0]:
        rows = [x for x in rows if x["AreaOfInterest"] == "CONUS"]  # the US file also has a "Total" row per week
    col = "DSCI" if metric == "dsci" else "D1"
    out = sorted((x["MapDate"], float(x[col])) for x in rows)
    if not out:
        raise SystemExit("No Drought Monitor data came back - check the state code.")
    return [(f"{d[:4]}-{d[4:6]}-{d[6:]}", v) for d, v in out]


def main():
    p = argparse.ArgumentParser(description="FSR on the U.S. Drought Monitor")
    p.add_argument("--state", type=str.upper, choices=sorted(FIPS), help="two-letter state (default: lower 48)")
    p.add_argument("--metric", default="dsci", choices=["dsci", "d1"])
    p.add_argument("--since", type=int, default=2000)
    p.add_argument("--window", type=int, default=12, help="weeks (default 12)")
    p.add_argument("--k", type=float, default=1.0)
    a = p.parse_args()

    rows = fetch(a.state, a.metric, a.since)
    dates, v = [d for d, _ in rows], [x for _, x in rows]
    where = a.state or "Lower 48"
    unit = "" if a.metric == "dsci" else "%"
    hi = v.index(max(v))
    print(f"\n{where} drought ({'DSCI 0-500' if a.metric == 'dsci' else '% in drought, D1+'}): "
          f"{len(v)} weeks, {dates[0]} to {dates[-1]}")
    print(f"Typical {statistics.median(v):g}{unit} | record {v[hi]:g}{unit} ({dates[hi]}) | latest {v[-1]:g}{unit} "
          f"| 3 months ago {v[-14]:g}{unit} | 1 year ago {v[-53]:g}{unit}")
    near_zero = sum(1 for x in v if x < (10 if a.metric == "dsci" else 2))
    if near_zero > len(v) * 0.03:
        print(f"WARNING: {near_zero} weeks near zero - FSR will break there. Try a later --since.")
    r = [calculate_predictability(v[i - a.window:i], a.k) for i in range(a.window, len(v) + 1)]
    e = dates[a.window - 1:]
    print(f"FSR (k={a.k}) overall {calculate_predictability(v, a.k):.2f}% | {a.window}-week window: typical "
          f"{statistics.median(r):.1f}%, lowest {min(r):.1f}% ({e[r.index(min(r))]}), latest {r[-1]:.1f}%")
    slug = (a.state or "us").lower()
    path = os.path.join(HERE, "output", f"drought_{slug}_{a.metric}_since{a.since}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{x:g}" for x in v))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
