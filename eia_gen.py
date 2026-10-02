"""
eia_gen.py - FSR on U.S. energy data straight from the EIA (needs free EIA_API_KEY in .env)

Get a key: https://www.eia.gov/opendata/register.php  ->  add  EIA_API_KEY=...  to .env

Presets (raw EIA series, fed straight into the FSR engine):
  crude        U.S. field production of crude oil, monthly (thousand barrels/day), since 1920
  crude_weekly U.S. crude oil production, weekly estimate, since 1983
  gas_storage  natural gas in underground storage, Lower 48, weekly (Bcf), since 2010
  gasoline     U.S. regular retail gasoline, weekly ($/gal), since 1990
  grid         daily electricity demand for a grid operator (MWh) - --region US48 / ERCO (Texas) /
               PJM / CISO (California) / MISO / NYIS ...

Run:
    python eia_gen.py --preset crude --since 2000
    python eia_gen.py --preset grid --region ERCO --since 2022      # Texas grid demand, daily
    python eia_gen.py --preset gas_storage --window 26
    python eia_gen.py --series PET.MCRFPUS2.M                       # any legacy EIA series id
"""
import argparse
import os
import statistics

import requests
from dotenv import load_dotenv

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = "https://api.eia.gov/v2"
PRESETS = {
    "crude": ("PET.MCRFPUS2.M", "U.S. field production of crude oil (thousand bbl/day, monthly)", 12),
    "crude_weekly": ("PET.WCRFPUS2.W", "U.S. crude oil production (thousand bbl/day, weekly)", 26),
    "gas_storage": ("NG.NW2_EPG0_SWO_R48_BCF.W", "Natural gas in storage, Lower 48 (Bcf, weekly)", 26),
    "gasoline": ("PET.EMM_EPMRU_PTE_NUS_DPG.W", "U.S. regular retail gasoline ($/gal, weekly)", 26),
}


def key():
    load_dotenv(os.path.join(HERE, ".env"))
    k = os.environ.get("EIA_API_KEY")
    if not k:
        raise SystemExit("EIA_API_KEY not set. Register free at https://www.eia.gov/opendata/register.php "
                         "and add EIA_API_KEY=... to .env")
    return k


def fetch_series_id(series_id, since=None):
    """Legacy series ids via the v2 compatibility route -> (dates, values) oldest first."""
    r = requests.get(f"{V2}/seriesid/{series_id}", params={"api_key": key()}, timeout=60).json()
    if "response" not in r:
        raise SystemExit(f"EIA error: {r.get('error') or r}")
    rows = [(d["period"], float(d["value"])) for d in r["response"]["data"]
            if d.get("value") not in (None, "")]
    rows.sort()
    if since:
        rows = [x for x in rows if x[0] >= since]
    return [a for a, _ in rows], [b for _, b in rows]


def fetch_grid(region, since):
    """Daily demand (MWh) for one balancing authority / region from the EIA-930 daily data."""
    params = {"api_key": key(), "frequency": "daily", "data[0]": "value", "facets[respondent][]": region,
              "facets[type][]": "D", "facets[timezone][]": "Eastern", "start": since,
              "sort[0][column]": "period", "sort[0][direction]": "asc", "length": 5000}
    out, offset = [], 0
    while True:
        params["offset"] = offset
        r = requests.get(f"{V2}/electricity/rto/daily-region-data/data/", params=params, timeout=60).json()
        if "response" not in r:
            raise SystemExit(f"EIA error: {r.get('error') or r}")
        batch = r["response"]["data"]
        out += [(d["period"], float(d["value"])) for d in batch if d.get("value") not in (None, "")]
        if len(batch) < 5000:
            break
        offset += 5000
    return [a for a, _ in out], [b for _, b in out]


def main():
    parser = argparse.ArgumentParser(description="FSR on EIA energy data")
    parser.add_argument("--preset", choices=list(PRESETS) + ["grid"], help="ready-made series")
    parser.add_argument("--series", help="any legacy EIA series id, e.g. PET.MCRFPUS2.M")
    parser.add_argument("--region", default="US48", help="grid preset: US48, ERCO, PJM, CISO, MISO, NYIS...")
    parser.add_argument("--since", default="2000", help="start (YYYY or YYYY-MM or YYYY-MM-DD)")
    parser.add_argument("--window", type=int, help="sliding window (default depends on frequency)")
    parser.add_argument("--k", type=float, default=1.0)
    args = parser.parse_args()
    if not (args.preset or args.series):
        parser.error("give --preset or --series")

    if args.preset == "grid":
        since = args.since if len(args.since) == 10 else (args.since + "-01-01")[:10]
        dates, values = fetch_grid(args.region, since)
        label, window, slug = f"Daily electricity demand, {args.region} (MWh)", args.window or 30, f"grid_{args.region}"
    else:
        sid, label, window = PRESETS[args.preset] if args.preset else (args.series, args.series, 12)
        dates, values = fetch_series_id(sid, args.since)
        window, slug = args.window or window, (args.preset or sid).lower().replace(".", "_")
    if len(values) < window + 2:
        raise SystemExit(f"Only {len(values)} points returned.")

    hi = values.index(max(values))
    print(f"\n{label}: {len(values)} points, {dates[0]} to {dates[-1]}")
    fmt = (lambda x: f"{x:,.0f}") if max(values) >= 1000 else (lambda x: f"{x:,.3g}")
    print(f"Latest {fmt(values[-1])} | high {fmt(values[hi])} ({dates[hi]}) | low {fmt(min(values))}")
    print(f"FSR (k={args.k}): {calculate_predictability(values, args.k):.1f}%")
    r = [calculate_predictability(values[i - window:i], args.k) for i in range(window, len(values) + 1)]
    lows = sorted(range(len(r)), key=r.__getitem__)[:3]
    print(f"{window}-point window: typical {statistics.median(r):.1f}%, latest {r[-1]:.1f}%, lowest "
          + ", ".join(f"{r[i]:.1f}% (ending {dates[i + window - 1]})" for i in lows))
    path = os.path.join(HERE, "output", f"eia_{slug}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{v:g}" for v in values))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
