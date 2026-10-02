"""
quake_gen.py - FSR on earthquake activity for any place (USGS catalog, free, no key)

Weekly earthquake counts within a radius of a place (or worldwide), from the USGS
ComCat catalog, fed straight into the FSR engine. Also saves the weekly max magnitude.

Pick a magnitude/radius that keeps most weeks above zero: FSR is relative to the
average, so a series of mostly-zero weeks gives meaningless readings (the script warns).

Run:
    python quake_gen.py --place "Los Angeles"                    # M2.5+ within 300 km, 10 years
    python quake_gen.py --place "Japan" --radius 800 --minmag 4
    python quake_gen.py --world --minmag 5 --years 20            # global M5+
"""
import argparse
import csv
import io
import os
import statistics
from datetime import date, datetime, timedelta

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def geocode(place):
    r = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": place, "count": 1},
                     timeout=20).json().get("results")
    if not r:
        raise SystemExit(f"Couldn't find a location for '{place}'.")
    return r[0]["latitude"], r[0]["longitude"], f"{r[0]['name']}, {r[0].get('country', '')}"


def events(start, end, minmag, lat=None, lon=None, radius_km=None):
    """(time, magnitude) for every event, fetched one year at a time (USGS caps 20k rows/call)."""
    out, s = [], start
    while s < end:
        e = min(end, s.replace(year=s.year + 1))
        params = {"format": "csv", "starttime": s.isoformat(), "endtime": e.isoformat(),
                  "minmagnitude": minmag, "orderby": "time-asc", "limit": 20000}
        if lat is not None:
            params.update(latitude=lat, longitude=lon, maxradiuskm=radius_km)
        text = requests.get(USGS, params=params, timeout=120).text
        for row in csv.DictReader(io.StringIO(text)):
            try:
                out.append((datetime.fromisoformat(row["time"].replace("Z", "+00:00")).date(), float(row["mag"])))
            except (KeyError, ValueError):
                pass
        s = e
    return out


def main():
    parser = argparse.ArgumentParser(description="FSR on weekly earthquake counts")
    parser.add_argument("--place", help="city/region name (geocoded)")
    parser.add_argument("--world", action="store_true", help="worldwide instead of one place")
    parser.add_argument("--radius", type=float, default=300, help="km around the place (default 300)")
    parser.add_argument("--minmag", type=float, default=2.5, help="minimum magnitude (default 2.5)")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--window", type=int, default=12, help="sliding window in weeks (default 12)")
    parser.add_argument("--k", type=float, default=1.0)
    args = parser.parse_args()
    if not args.place and not args.world:
        parser.error("give --place NAME or --world")

    end = date.today()
    start = end.replace(year=end.year - args.years)
    if args.world:
        label, ev = f"worldwide M{args.minmag}+", events(start, end, args.minmag)
    else:
        lat, lon, name = geocode(args.place)
        label = f"M{args.minmag}+ within {args.radius:.0f} km of {name}"
        ev = events(start, end, args.minmag, lat, lon, args.radius)

    weeks = {}
    monday = start - timedelta(days=start.weekday())
    while monday <= end - timedelta(days=7):
        weeks[monday] = [0, 0.0]
        monday += timedelta(days=7)
    for d, mag in ev:
        wk = d - timedelta(days=d.weekday())
        if wk in weeks:
            weeks[wk][0] += 1
            weeks[wk][1] = max(weeks[wk][1], mag)
    labels = [str(w) for w in weeks]
    counts = [c for c, _ in weeks.values()]
    zero_share = counts.count(0) / len(counts)

    print(f"\nEarthquakes, {label}: {len(ev):,} events, {len(counts)} full weeks ({labels[0]} to {labels[-1]})")
    big = max(ev, key=lambda x: x[1]) if ev else None
    if big:
        print(f"Largest: M{big[1]} on {big[0]} | busiest week: {max(counts)} quakes ({labels[counts.index(max(counts))]})")
    if zero_share > 0.2:
        print(f"WARNING: {zero_share:.0%} of weeks have zero quakes - FSR readings will be noisy. "
              f"Widen --radius or lower --minmag.")
    print(f"FSR (k={args.k}): {calculate_predictability(counts, args.k):.1f}%")
    r = [calculate_predictability(counts[i - args.window:i], args.k) for i in range(args.window, len(counts) + 1)]
    lows = sorted(range(len(r)), key=r.__getitem__)[:3]
    print(f"{args.window}-week window: typical {statistics.median(r):.1f}%, latest {r[-1]:.1f}%, lowest "
          + ", ".join(f"{r[i]:.1f}% (week of {labels[i + args.window - 1]})" for i in lows))

    slug = "world" if args.world else args.place.lower().replace(" ", "_")
    path = os.path.join(HERE, "output", f"quakes_{slug}_weekly.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(map(str, counts)))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
