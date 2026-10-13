"""
groundwater_gen.py - FSR on underground water storage for any place on Earth (NASA, from space)

Source: NASA GLDAS Catchment model, daily, 0.25 deg (GLDAS_CLSM025_DA1_D v2.2), which
assimilates the GRACE / GRACE-FO gravity satellites. Variable GWS_tavg = groundwater
storage in mm of water. Unlike raw GRACE (anomalies that cross zero), this is an absolute,
always-positive amount - so it works in the FSR engine. Daily since Feb 2003, no gaps.

Pulls ONE day per step (default: the 1st of every month) through NASA's OPeNDAP service,
averaging a small block of grid cells around the point. Needs EARTHDATA_TOKEN in .env and the
"NASA GESDISC DATA ARCHIVE" app approved in your Earthdata profile.

Model data, not a single well: say "NASA satellite-based estimate".

Run:
    python groundwater_gen.py --preset high_plains            # Ogallala aquifer, SW Kansas
    python groundwater_gen.py --preset central_valley --step 7  # weekly instead of monthly
    python groundwater_gen.py --lat 31.8 --lon -106.5 --name el_paso
"""
import argparse
import os
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
SHORT_NAME, VERSION = "GLDAS_CLSM025_DA1_D", "2.2"
FIRST_DAY = date(2003, 2, 1)
PRESETS = {  # name: (lat, lon, label)
    "high_plains": (37.9, -100.9, "High Plains / Ogallala aquifer (SW Kansas)"),
    "texas_panhandle": (34.6, -101.9, "Texas Panhandle (Ogallala, near Lubbock/Amarillo)"),
    "central_valley": (36.6, -119.8, "California Central Valley (near Fresno)"),
    "southwest": (32.3, -106.8, "Mesilla Basin, New Mexico (near Las Cruces)"),
    "phoenix": (33.4, -112.1, "Phoenix, Arizona"),
}


def session():
    load_dotenv(os.path.join(HERE, ".env"))
    tok = os.environ.get("EARTHDATA_TOKEN")
    if not tok:
        raise SystemExit("EARTHDATA_TOKEN not set in .env (Earthdata profile -> Generate Token).")
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + tok
    return s


def collection_id():
    c = requests.get("https://cmr.earthdata.nasa.gov/search/collections.json",
                     params={"short_name": SHORT_NAME, "version": VERSION}, timeout=60).json()
    return c["feed"]["entry"][0]["id"]


def latest_day():
    g = requests.get("https://cmr.earthdata.nasa.gov/search/granules.json",
                     params={"short_name": SHORT_NAME, "version": VERSION, "sort_key": "-start_date",
                             "page_size": 1}, timeout=60).json()
    return date.fromisoformat(g["feed"]["entry"][0]["time_start"][:10])


def cell(lat, lon):
    """Grid indices on the 0.25 deg grid (lat -59.875..89.875, lon -179.875..179.875)."""
    return round((lat + 59.875) / 0.25), round((lon + 179.875) / 0.25)


def read_day(s, cid, day, i, j, r):
    title = f"{SHORT_NAME}.{VERSION}:{SHORT_NAME}.A{day:%Y%m%d}.022.nc4"
    url = f"https://opendap.earthdata.nasa.gov/collections/{cid}/granules/" + requests.utils.quote(title, safe="")
    for _ in range(3):
        try:
            t = s.get(url + ".dap.csv", params={"dap4.ce": f"/GWS_tavg[0][{i - r}:{i + r}][{j - r}:{j + r}]"},
                      timeout=120).text
            vals = [float(x) for line in t.splitlines()[1:] for x in line.split(",")[1:]
                    if x.strip() and float(x) > -9000]
            return day, (statistics.mean(vals) if vals else None)
        except Exception:
            continue
    return day, None


def main():
    p = argparse.ArgumentParser(description="FSR on NASA satellite-based groundwater storage")
    p.add_argument("--preset", choices=list(PRESETS))
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--name", help="file label when using --lat/--lon")
    p.add_argument("--step", type=int, default=0, help="days between samples (default 0 = 1st of each month)")
    p.add_argument("--radius", type=int, default=2, help="grid cells around the point to average (2 = 5x5)")
    p.add_argument("--window", type=int, default=12)
    p.add_argument("--k", type=float, default=1.0)
    a = p.parse_args()
    if a.preset:
        lat, lon, label = PRESETS[a.preset]
        slug = a.preset
    elif a.lat is not None and a.lon is not None:
        lat, lon, label, slug = a.lat, a.lon, f"{a.lat}, {a.lon}", a.name or f"{a.lat}_{a.lon}"
    else:
        p.error("give --preset or --lat/--lon")

    end = latest_day()
    days, d = [], FIRST_DAY
    while d <= end:
        days.append(d)
        d = d + timedelta(days=a.step) if a.step else (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    s, cid, (i, j) = session(), collection_id(), cell(lat, lon)
    print(f"Pulling {len(days)} samples for {label} ({days[0]} to {days[-1]})...")
    with ThreadPoolExecutor(8) as ex:
        got = sorted(ex.map(lambda dd: read_day(s, cid, dd, i, j, a.radius), days))
    rows = [(dd, v) for dd, v in got if v is not None]
    if len(rows) < a.window + 2:
        raise SystemExit(f"Only {len(rows)} readings came back - check the Earthdata app approval.")
    labels, v = [str(dd) for dd, _ in rows], [x for _, x in rows]

    lo, hi = v.index(min(v)), v.index(max(v))
    print(f"\nGroundwater storage, {label}: {len(v)} readings ({labels[0]} to {labels[-1]}), mm of water")
    print(f"Latest {v[-1]:,.0f} | high {v[hi]:,.0f} ({labels[hi]}) | low {v[lo]:,.0f} ({labels[lo]}) | "
          f"change since start {100 * (v[-1] / v[0] - 1):+.1f}%")
    print(f"FSR (k={a.k}): {calculate_predictability(v, a.k):.1f}%")
    r = [calculate_predictability(v[k - a.window:k], a.k) for k in range(a.window, len(v) + 1)]
    lows = sorted(range(len(r)), key=r.__getitem__)[:3]
    print(f"{a.window}-point window: typical {statistics.median(r):.1f}%, latest {r[-1]:.1f}%, lowest "
          + ", ".join(f"{r[k]:.1f}% (ending {labels[k + a.window - 1]})" for k in lows))
    path = os.path.join(HERE, "output", f"groundwater_{slug}{'_step' + str(a.step) if a.step else ''}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{x:.1f}" for x in v))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
