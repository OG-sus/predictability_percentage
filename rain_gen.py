"""
rain_gen.py - FSR on NASA satellite rainfall (GPM IMERG) for any place on Earth

NASA's IMERG merges every rain-measuring satellite into one global grid (0.1 deg, ~10 km).
  --hours  (default) half-hourly rain rate, "Early" run - only ~4 hours behind real time.
           For a live storm hitting a city.
  --daily  daily totals, "Late" run - through yesterday. For a rainy season / multi-month view.
Pulls just the grid cells around your point through NASA's OPeNDAP service (one small request
per time step). Needs EARTHDATA_TOKEN in .env and the "NASA GESDISC DATA ARCHIVE" app approved.

Rain has a lot of exact zeros (dry hours), and FSR breaks near zero. Two ways around it:
  - pick a period when it's raining (a storm, a monsoon), or
  - --cumulative: running storm total (the "how much has fallen so far" curve), which never
    returns to zero. Say "total rain so far" in the script if you use it.

Run:
    python rain_gen.py --place "Tampa" --hours 72                 # last 3 days, every 30 min
    python rain_gen.py --lat 13.08 --lon 80.27 --name chennai --daily 120
    python rain_gen.py --place "Houston" --hours 48 --cumulative
"""
import argparse
import os
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
CMR = "https://cmr.earthdata.nasa.gov/search"
PRODUCTS = {  # mode: (short_name, variable path, unit)
    "hours": ("GPM_3IMERGHHE", "/Grid/precipitation", "mm/hr"),
    "daily": ("GPM_3IMERGDL", "/precipitation", "mm/day"),
}


def session():
    load_dotenv(os.path.join(HERE, ".env"))
    tok = os.environ.get("EARTHDATA_TOKEN")
    if not tok:
        raise SystemExit("EARTHDATA_TOKEN not set in .env (Earthdata profile -> Generate Token).")
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + tok
    return s


def geocode(place):
    r = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": place, "count": 1},
                     timeout=20).json().get("results")
    if not r:
        raise SystemExit(f"Couldn't find '{place}'.")
    return r[0]["latitude"], r[0]["longitude"], f"{r[0]['name']}, {r[0].get('country', '')}"


def granules(short_name, start, end):
    """[(start_time, title)] for every granule in the window, oldest first."""
    c = requests.get(f"{CMR}/collections.json", params={"short_name": short_name}, timeout=60).json()
    cid = sorted(c["feed"]["entry"], key=lambda x: x["version_id"])[-1]["id"]
    out, page = [], 1
    while True:
        g = requests.get(f"{CMR}/granules.json", params={
            "collection_concept_id": cid, "temporal": f"{start:%Y-%m-%dT%H:%M:%SZ},{end:%Y-%m-%dT%H:%M:%SZ}",
            "sort_key": "start_date", "page_size": 2000, "page_num": page}, timeout=120).json()["feed"]["entry"]
        out += [(x["time_start"], x["title"]) for x in g]
        if len(g) < 2000:
            break
        page += 1
    return cid, out


def read(s, cid, title, var, i, j, r):
    url = f"https://opendap.earthdata.nasa.gov/collections/{cid}/granules/" + requests.utils.quote(title, safe="")
    for _ in range(3):
        try:
            t = s.get(url + ".dap.csv", params={"dap4.ce": f"{var}[0][{i - r}:{i + r}][{j - r}:{j + r}]"},
                      timeout=120).text
            vals = [float(x) for line in t.splitlines()[1:] for x in line.split(",")[1:]
                    if x.strip() and float(x) >= 0]
            return statistics.mean(vals) if vals else None
        except Exception:
            continue
    return None


def main():
    p = argparse.ArgumentParser(description="FSR on NASA GPM IMERG satellite rainfall")
    p.add_argument("--place", help="city or region (geocoded)")
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--name", help="file label with --lat/--lon")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--hours", type=int, default=72, help="half-hourly, last N hours (default 72)")
    g.add_argument("--daily", type=int, help="daily totals for the last N days instead")
    p.add_argument("--radius", type=int, default=1, help="grid cells around the point (1 = 3x3, ~30 km)")
    p.add_argument("--cumulative", action="store_true", help="running total instead of the rate")
    p.add_argument("--window", type=int, help="sliding window (default: 6 hours / 7 days)")
    p.add_argument("--k", type=float, default=1.0)
    a = p.parse_args()
    if a.place:
        lat, lon, label = geocode(a.place)
        slug = a.place.lower().replace(" ", "_")
    elif a.lat is not None and a.lon is not None:
        lat, lon, label, slug = a.lat, a.lon, f"{a.lat}, {a.lon}", a.name or f"{a.lat}_{a.lon}"
    else:
        p.error("give --place or --lat/--lon")

    mode = "daily" if a.daily else "hours"
    short, var, unit = PRODUCTS[mode]
    now = datetime.now(timezone.utc)
    start = now - (timedelta(days=a.daily) if a.daily else timedelta(hours=a.hours))
    cid, gl = granules(short, start, now)
    if not gl:
        raise SystemExit("No IMERG files in that window yet.")
    i, j = round((lon + 179.95) / 0.1), round((lat + 89.95) / 0.1)   # IMERG grid is [time][lon][lat]
    s = session()
    print(f"Pulling {len(gl)} {mode} IMERG steps for {label}...")
    with ThreadPoolExecutor(8) as ex:
        vals = list(ex.map(lambda t: read(s, cid, t[1], var, i, j, a.radius), gl))
    rows = [(t[0][:16].replace("T", " "), v) for t, v in zip(gl, vals) if v is not None]
    if not rows:
        raise SystemExit("No readings came back - check the Earthdata app approval.")
    stamps, v = [x for x, _ in rows], [x for _, x in rows]
    total = sum(v) * (0.5 if mode == "hours" else 1)  # half-hourly rates are mm/hr over 30 min
    hi = v.index(max(v))
    print(f"\nIMERG rainfall, {label}: {len(v)} {mode} readings, {stamps[0]} to {stamps[-1]} UTC")
    print(f"Peak {v[hi]:.1f} {unit} ({stamps[hi]}) | total {total:.0f} mm | "
          f"dry steps {sum(1 for x in v if x < 0.05) / len(v):.0%}")
    if a.cumulative:
        run, v = 0.0, []
        for x in (x for _, x in rows):
            run += x * (0.5 if mode == "hours" else 1)
            v.append(round(run, 2))
        unit = "mm so far"
    elif sum(1 for x in v if x < 0.05) / len(v) > 0.2:
        print("WARNING: lots of dry (zero) steps - FSR will be noisy. Use a rainier period or --cumulative.")
    w = a.window or (12 if mode == "hours" else 7)
    usable = [x for x in v]
    r = [calculate_predictability(usable[k - w:k], a.k) for k in range(w, len(usable) + 1)]
    if r:
        lo = r.index(min(r))
        print(f"FSR (k={a.k}) {'cumulative ' if a.cumulative else ''}| {w}-step window: typical "
              f"{statistics.median(r):.1f}%, lowest {r[lo]:.1f}% ({stamps[lo + w - 1]}), latest {r[-1]:.1f}%")
    path = os.path.join(HERE, "output", f"rain_{slug}_{mode}{'_cumulative' if a.cumulative else ''}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{x:.2f}" for x in v))
    print(f"\nSaved {path}  ({unit})")


if __name__ == "__main__":
    main()
