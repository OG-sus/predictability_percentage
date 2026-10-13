"""
buoy_gen.py - FSR on a NOAA ocean buoy's sensors (the hurricane Shorts)

NOAA's National Data Buoy Center keeps the last 45 days of readings for each buoy (free, no
key). Saves one reading per hour, oldest first, for wave height, wind gusts or air pressure.
Waves and gusts crack the engine during storms; pressure barely does (it's a big number that
moves a little), so use pressure as a caption fact, not the chart.

Buoys used so far: 42039 (Pensacola), 42012 (Orange Beach, AL), 42001 (mid-Gulf),
42002 (west Gulf), 42036 (west of Tampa), 42055 (Bay of Campeche). Map: https://www.ndbc.noaa.gov

Run:
    python buoy_gen.py 42039                    # wave height, hourly, last 45 days
    python buoy_gen.py 42001 --sensor GST       # wind gusts
    python buoy_gen.py 42039 --sensor PRES
"""
import argparse
import os
import statistics

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
UNITS = {"WVHT": "m", "GST": "m/s", "WSPD": "m/s", "PRES": "mb", "WTMP": "C"}


def hourly(station, sensor):
    lines = requests.get(f"https://www.ndbc.noaa.gov/data/realtime2/{station}.txt", timeout=30).text.splitlines()
    if not lines or not lines[0].startswith("#"):
        raise SystemExit(f"No realtime data for buoy {station}.")
    hdr = lines[0].lstrip("#").split()
    if sensor not in hdr:
        raise SystemExit(f"Buoy {station} has no {sensor}. Columns: {' '.join(hdr)}")
    i = hdr.index(sensor)
    seen, out = set(), []
    for row in reversed([ln.split() for ln in lines[2:]]):  # file is newest-first
        if row[i] == "MM":
            continue
        stamp = f"{row[0]}-{row[1]}-{row[2]} {row[3]}:{row[4]}"
        if stamp[:-3] not in seen:  # first reading of each hour
            seen.add(stamp[:-3])
            out.append((stamp, float(row[i])))
    return out


def main():
    p = argparse.ArgumentParser(description="FSR on a NOAA buoy sensor")
    p.add_argument("station")
    p.add_argument("--sensor", default="WVHT", choices=list(UNITS))
    p.add_argument("--window", type=int, default=24, help="hours (default 24)")
    p.add_argument("--k", type=float, default=1.0)
    a = p.parse_args()

    rows = hourly(a.station, a.sensor)
    stamps, v = [s for s, _ in rows], [x for _, x in rows]
    u = UNITS[a.sensor]
    hi, lo = v.index(max(v)), v.index(min(v))
    print(f"\nBuoy {a.station} {a.sensor}: {len(v)} hourly readings, {stamps[0]} to {stamps[-1]} UTC")
    print(f"Normal (median) {statistics.median(v):g} {u} | max {v[hi]:g} ({stamps[hi]}) | "
          f"min {v[lo]:g} ({stamps[lo]}) | latest {v[-1]:g} {u}")
    r = [calculate_predictability(v[i - a.window:i], a.k) for i in range(a.window, len(v) + 1)]
    e = stamps[a.window - 1:]
    print(f"FSR (k={a.k}) overall {calculate_predictability(v, a.k):.2f}% | {a.window}-hour window: typical "
          f"{statistics.median(r):.1f}%, lowest {min(r):.1f}% ({e[r.index(min(r))]}), latest {r[-1]:.1f}%")
    path = os.path.join(HERE, "output", f"buoy_{a.station}_{a.sensor.lower()}_hourly.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{x:g}" for x in v))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
