"""
fire_gen.py - FSR on NASA FIRMS satellite fire detections (any region, monthly since 2000)

FIRMS counts every active-fire hotspot NASA's satellites see. MODIS (Terra/Aqua) runs from
Nov 2000: the archive ("SP") through a few months ago, then near-real-time ("NRT") to today,
so one series covers 26 years. VIIRS (--source VIIRS_SNPP) is sharper, from 2012.

Fire seasons spike every year and El Nino years spike harder (Indonesia 2015, 2019, 2023), so
monthly counts make the classic several-spikes chart. Regions are lat/lon boxes, not borders:
the Indonesia box also takes in Malaysian Borneo, Timor-Leste and Singapore.

Needs FIRMS_MAP_KEY in .env (free: firms.modaps.eosdis.nasa.gov/api/map_key). Day counts are
cached in output/firms_cache/, so a rerun only downloads the new days.

Run:
    python fire_gen.py --preset indonesia             # monthly since 2000 (first run ~35 min)
    python fire_gen.py --preset borneo --since 2012
    python fire_gen.py --bbox -125,32,-114,42 --name california
    python fire_gen.py --preset indonesia --daily 120 # last 120 days, day by day
"""
import argparse
import csv
import io
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests
from dotenv import dotenv_values

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://firms.modaps.eosdis.nasa.gov/api"
CHUNK = 5  # the area API returns at most 5 days per call
PRESETS = {  # west,south,east,north
    "indonesia": "94,-11,141,6",
    "borneo": "108.5,-4.5,119.5,7.5",
    "sumatra": "95,-6,106.5,6",
    "california": "-125,32,-114,42",
    "amazon": "-74,-18,-44,5",
    "canada": "-141,48,-52,70",
    "australia": "112,-44,154,-10",
}


def key():
    k = dotenv_values(os.path.join(HERE, ".env")).get("FIRMS_MAP_KEY") or os.environ.get("FIRMS_MAP_KEY")
    if not k:
        raise SystemExit("Put FIRMS_MAP_KEY=... in .env (free key: firms.modaps.eosdis.nasa.gov/api/map_key).")
    return k


def availability(k, source):
    """(archive start, archive end, live start, live end) for MODIS or VIIRS_SNPP."""
    rows = {r["data_id"]: r for r in csv.DictReader(io.StringIO(
        requests.get(f"{API}/data_availability/csv/{k}/all", timeout=60).text))}
    sp, nrt = rows[f"{source}_SP"], rows[f"{source}_NRT"]
    d = date.fromisoformat
    return d(sp["min_date"]), d(sp["max_date"]), d(nrt["min_date"]), d(nrt["max_date"])


def wait_for_quota(k):
    """FIRMS allows 5,000 transactions per 10 minutes per key - pause before hitting it."""
    while True:
        try:
            s = requests.get(f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={k}",
                             timeout=60).json()
            if s["current_transactions"] < s["transaction_limit"] - 700:  # each 5-day call costs ~9
                return
        except Exception:
            return
        print("  (pausing 60s for the FIRMS rate limit...)")
        time.sleep(60)


def fetch_chunk(k, product, bbox, start):
    """Fire detections per day for CHUNK days from `start` -> {date: count}."""
    url = f"{API}/area/csv/{k}/{product}/{bbox}/{CHUNK}/{start}"
    attempt = 0
    while attempt < 4:
        r = requests.get(url, timeout=300)
        if r.ok and r.text.startswith("latitude"):
            counts = {}
            for row in csv.DictReader(io.StringIO(r.text)):
                counts[row["acq_date"]] = counts.get(row["acq_date"], 0) + 1
            return counts
        if "transaction limit" in r.text:  # rate limit, not a real failure: wait it out
            time.sleep(60)
            continue
        attempt += 1
        time.sleep(10 * attempt)
    raise RuntimeError(f"FIRMS kept failing for {product} {start}: {r.status_code} {r.text[:80]}")


def day_counts(k, source, bbox, slug, first, last):
    """Daily detection counts first..last, from cache plus whatever's missing."""
    sp0, sp1, nrt0, nrt1 = availability(k, source)
    first, last = max(first, sp0), min(last, nrt1)
    cache_path = os.path.join(HERE, "output", "firms_cache", f"{slug}_{source}.json")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    cache.pop("_through", None)  # old bookkeeping format
    done = set(cache.pop("_chunks", []))  # "PRODUCT|start" for every chunk already downloaded

    # Chunks sit on a fixed 5-day grid from the product's first day, so reruns line up exactly.
    jobs = []
    for product, lo, hi in ((f"{source}_SP", first, min(last, sp1)), (f"{source}_NRT", max(first, nrt0, sp1 + timedelta(1)), last)):
        grid0 = sp0 if product.endswith("SP") else max(nrt0, sp1 + timedelta(1))
        start = grid0 + timedelta(((lo - grid0).days // CHUNK) * CHUNK)
        while start <= hi:
            # live (NRT) days in the last week can still fill in, so refetch those every run
            fresh = product.endswith("NRT") and start + timedelta(CHUNK) > last - timedelta(7)
            if f"{product}|{start}" not in done or fresh:
                jobs.append((product, start))
            start += timedelta(CHUNK)
    if jobs:
        print(f"Downloading {len(jobs)} x {CHUNK}-day chunks from NASA FIRMS ({len(jobs) * CHUNK} days)...")
    days = {d: c for d, c in cache.items() if not d.startswith("_")}
    step = 40
    for i in range(0, len(jobs), step):
        wait_for_quota(k)
        batch = jobs[i:i + step]
        with ThreadPoolExecutor(6) as ex:
            for (product, start), counts in zip(batch, ex.map(lambda j: fetch_chunk(k, j[0], bbox, j[1]), batch)):
                end = start + timedelta(CHUNK - 1)
                for n in range(CHUNK):  # zero-fill the chunk's days, then add the fires it saw
                    days[str(start + timedelta(n))] = 0
                for dd, c in counts.items():
                    if start <= date.fromisoformat(dd) <= end:
                        days[dd] = c
                done.add(f"{product}|{start}")
        if (i // step) % 5 == 4 or i + step >= len(jobs):
            print(f"  {min(i + step, len(jobs))}/{len(jobs)} chunks")
        json.dump({**days, "_chunks": sorted(done)}, open(cache_path, "w"))
    return {date.fromisoformat(d): c for d, c in days.items() if first <= date.fromisoformat(d) <= last}


def main():
    p = argparse.ArgumentParser(description="FSR on NASA FIRMS fire detections")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--preset", choices=sorted(PRESETS))
    g.add_argument("--bbox", help="west,south,east,north")
    p.add_argument("--name", help="file label when using --bbox")
    p.add_argument("--source", default="MODIS", choices=["MODIS", "VIIRS_SNPP"])
    p.add_argument("--since", type=int, default=2001)
    p.add_argument("--daily", type=int, metavar="N", help="last N days, one point per day (instead of monthly)")
    p.add_argument("--window", type=int, help="sliding window (default 12 months / 7 days)")
    p.add_argument("--k", type=float, default=1.0)
    a = p.parse_args()

    k = key()
    bbox = PRESETS.get(a.preset) or a.bbox
    slug = a.preset or a.name or bbox.replace(",", "_")
    today = date.today()
    first = today - timedelta(a.daily) if a.daily else date(a.since, 1, 1)
    days = day_counts(k, a.source, bbox, slug, first, today - timedelta(1))

    if a.daily:
        labels = sorted(days)
        v = [days[d] for d in labels]
        labels = [str(d) for d in labels]
        unit, window = "day", a.window or 7
    else:
        months = {}
        for d, c in days.items():
            months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
        keys = sorted(months)
        labels, v = [f"{y}-{m:02d}" for y, m in keys], [months[x] for x in keys]
        unit, window = "month", a.window or 12

    hi = v.index(max(v))
    print(f"\n{slug} fire detections ({a.source}) per {unit}: {len(v)} {unit}s, {labels[0]} to {labels[-1]}"
          + (" (this month is partial)" if not a.daily else ""))
    print(f"Typical {statistics.median(v):,.0f} | record {v[hi]:,} ({labels[hi]}) | latest {v[-1]:,}")
    if not a.daily:
        same = sorted(((v[i], labels[i]) for i in range(len(v)) if labels[i][5:] == labels[-2][5:]), reverse=True)
        print(f"Biggest {labels[-2][5:]}s (last full month): " + ", ".join(f"{m} ({c:,})" for c, m in same[:5]))
    zeros = sum(1 for x in v if x == 0)
    if zeros > len(v) * 0.03:
        print(f"WARNING: {zeros} zero {unit}s - FSR breaks near zero. Use a bigger region or monthly.")
    r = [calculate_predictability(v[i - window:i], a.k) for i in range(window, len(v) + 1)]
    e = labels[window - 1:]
    print(f"FSR (k={a.k}) overall {calculate_predictability(v, a.k):.2f}% | {window}-{unit} window: typical "
          f"{statistics.median(r):.1f}%, lowest {min(r):.1f}% ({e[r.index(min(r))]}), latest {r[-1]:.1f}%")
    path = os.path.join(HERE, "output", f"fires_{slug}_{a.source.lower()}_{'daily' if a.daily else 'monthly'}.txt")
    with open(path, "w") as f:
        f.write(", ".join(str(x) for x in v))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
