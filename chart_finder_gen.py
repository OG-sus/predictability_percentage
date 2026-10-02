"""
chart_finder_gen.py - find the long time series where the FSR engine has the most to show

Data first, not news first. Pulls hundreds of LONG series from any field and ranks
them by how good they'd look in the website calculator (line on top, sliding window
below):

  - long history          (150+ points, ideally hundreds)
  - several real cracks   (distinct deep dips in the sliding window, not one spike at the end)
  - something current     (the window moving now, or the value at an unusual level)

Sources:
  fred    - popular, still-updating FRED series across ~35 topics (economy, energy, health,
            transport, credit, food, trade...), one per series family
  science - NOAA Mauna Loa CO2 (monthly since 1958), SILSO sunspots (monthly since 1749),
            TSA checkpoint travel (weekly since 2019)
  kaggle  - recently updated Kaggle datasets that contain a clean one-row-per-date series
            (needs KAGGLE_API_TOKEN in .env)

Every top result's series is saved to output/chartfinder/<name>.txt, ready to paste.

Run:
    python chart_finder_gen.py                     # fred + science + kaggle, top 20
    python chart_finder_gen.py --only fred science # skip kaggle (faster)
    python chart_finder_gen.py --top 40
"""
import argparse
import csv
import glob
import io
import json
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output", "chartfinder")
K = 1.0
MIN_POINTS = 150

FRED_TOPICS = [
    "price", "index", "rate", "sales", "production", "employment", "consumer", "energy", "housing",
    "trade", "health", "transportation", "manufacturing", "retail", "credit", "debt", "wage", "income",
    "inventory", "travel", "food", "agriculture", "vehicle", "electricity", "construction", "business",
    "bank", "loans", "delinquency", "bankruptcy", "exports", "imports", "commodity", "metals", "oil",
]
KAGGLE_QUERIES = ["daily updated", "time series daily", "historical daily data", "monthly time series",
                  "weekly data", "daily prices", "daily statistics"]


def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:60].lower()


# ── Scoring ──────────────────────────────────────────────────────────────────
def evaluate(source, name, dates, values, command=""):
    """How chart-worthy is this series for the calculator? None if too short/flat."""
    vals = [float(v) for v in values]
    n = len(vals)
    # The score is relative to the mean, so series that touch or cross zero (rate spreads,
    # growth rates) give meaningless 0% lows - skip them.
    if n < MIN_POINTS or statistics.pstdev(vals) == 0 or min(vals) <= 0:
        return None
    window = max(6, min(60, n // 25))
    roll = [calculate_predictability(vals[i - window:i], K) for i in range(window, n + 1)]
    med = statistics.median(roll)
    # distinct cracks: dips at least 15 points below normal, separated by 2 windows
    cracks, last_i = [], -10 ** 9
    for i in sorted(range(len(roll)), key=roll.__getitem__):
        if roll[i] > med - 15:
            break
        if all(abs(i - j) > 2 * window for j, _ in cracks):
            cracks.append((i, roll[i]))
    cracks.sort()
    tail = len(roll) - max(1, len(roll) // 10)
    only_end_spike = len(cracks) == 1 and cracks[0][0] >= tail
    recent_crack = any(i >= tail for i, _ in cracks)
    at_extreme = vals[-1] >= max(vals) or vals[-1] <= min(vals)
    depth = med - min(roll)
    score = (min(len(cracks), 6) * 10 + min(depth, 60) * 0.5 + (10 if recent_crack and len(cracks) >= 2 else 0)
             + (5 if at_extreme else 0) + min(n, 1000) / 100 - (25 if only_end_spike else 0))
    if only_end_spike:
        shape = "one spike at the end"
    elif recent_crack:
        shape = f"{len(cracks)} cracks, one happening now"
    else:
        shape = f"{len(cracks)} cracks"
    return {
        "source": source, "name": name, "points": n, "span": f"{dates[0]} .. {dates[-1]}", "window": window,
        "cracks": len(cracks), "crack_dates": [dates[i + window - 1] for i, _ in cracks[:6]],
        "normal": round(med, 1), "lowest": round(min(roll), 1), "latest": round(roll[-1], 1),
        "shape": shape, "at_extreme": at_extreme, "score": round(score, 1), "command": command,
        "_values": vals,
    }


# ── Sources ──────────────────────────────────────────────────────────────────
def scan_fred(max_series=250):
    from FRED_gen import fetch_series, fred
    cutoff = (date.today() - timedelta(days=120)).isoformat()
    picked, families = [], set()
    for topic in FRED_TOPICS:
        try:
            found = fred("series/search", search_text=topic, order_by="popularity", sort_order="desc", limit=100)
        except Exception as e:
            log(f"  fred search '{topic}': {e}")
            continue
        for s in found.get("seriess", []):
            fam = s["id"][:6]
            if (s["frequency_short"] in ("D", "W", "M", "Q") and s["observation_end"] >= cutoff
                    and s["observation_start"] <= "2012-01-01" and s.get("popularity", 0) >= 25
                    and fam not in families):
                families.add(fam)
                picked.append(s)
        time.sleep(0.3)
    picked = sorted(picked, key=lambda s: -s.get("popularity", 0))[:max_series]
    log(f"  FRED: scoring {len(picked)} series")
    since = {"D": "2018", "W": "2006", "M": "1990", "Q": "1980"}
    for s in picked:
        try:
            _, d, v = fetch_series(s["id"], since=since[s["frequency_short"]])
            yield evaluate("fred", f"{s['id']} - {s['title'][:70]}", d, v,
                           f"python FRED_gen.py {s['id']} --since {d[0][:4]}")
        except Exception as e:
            log(f"  skip {s['id']}: {e}")
        time.sleep(0.25)


def scan_science():
    hdr = {"User-Agent": "predictability-api.com chart finder"}
    # NOAA Mauna Loa CO2, monthly
    try:
        rows = [l.split(",") for l in requests.get("https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv",
                                                    headers=hdr, timeout=60).text.splitlines()
                if l and not l.startswith("#") and l[0].isdigit()]
        d = [f"{int(r[0])}-{int(r[1]):02d}" for r in rows]
        v = [float(r[3]) for r in rows]
        yield evaluate("science", "CO2 at Mauna Loa (NOAA, ppm, monthly)", d, v, "NOAA GML co2_mm_mlo.csv")
    except Exception as e:
        log(f"  skip CO2: {e}")
    # SILSO monthly sunspot number
    try:
        rows = [l.split(";") for l in requests.get("https://www.sidc.be/SILSO/INFO/snmtotcsv.php",
                                                    headers=hdr, timeout=60).text.splitlines() if l.strip()]
        rows = [r for r in rows if float(r[3]) >= 0][-1200:]   # last 100 years, drop missing (-1)
        d = [f"{int(r[0])}-{int(r[1]):02d}" for r in rows]
        v = [float(r[3]) + 1 for r in rows]                      # +1 keeps zero-sunspot months scoreable
        yield evaluate("science", "Sunspots (SILSO, monthly, last 100 years)", d, v, "SILSO snmtotcsv.php")
    except Exception as e:
        log(f"  skip sunspots: {e}")
    # TSA weekly
    try:
        from tsa_gen import fetch_daily, weekly_totals
        w = weekly_totals(fetch_daily(2019))
        yield evaluate("science", "TSA airport travelers (weekly)", [str(x) for x in w], list(w.values()),
                       "python tsa_gen.py --since 2019")
    except Exception as e:
        log(f"  skip TSA: {e}")


def scan_kaggle(max_datasets=25, max_mb=30):
    """Recently updated Kaggle datasets with a clean one-row-per-date column + numeric columns."""
    import pandas as pd
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
    exe = os.path.join(HERE, ".venv", "Scripts", "kaggle.exe")
    if not os.path.exists(exe) or not os.environ.get("KAGGLE_API_TOKEN"):
        log("  skip kaggle: no kaggle CLI or KAGGLE_API_TOKEN")
        return
    since = (date.today() - timedelta(days=60)).isoformat()
    refs = []
    for q in KAGGLE_QUERIES:
        r = subprocess.run([exe, "datasets", "list", "-s", q, "--sort-by", "updated", "--csv"], capture_output=True,
                           text=True, env=dict(os.environ), encoding="utf-8")
        for x in csv.DictReader(io.StringIO(r.stdout)):
            try:
                if x["lastUpdated"] >= since and int(x["size"]) <= max_mb * 1e6 and x["ref"] not in refs:
                    refs.append(x["ref"])
            except (KeyError, ValueError):
                pass
    log(f"  Kaggle: checking {min(len(refs), max_datasets)} recently updated datasets")
    for ref in refs[:max_datasets]:
        dest = os.path.join(HERE, "output", "kaggle", ref.split("/")[1])
        if not glob.glob(os.path.join(dest, "**", "*.csv"), recursive=True):
            subprocess.run([exe, "datasets", "download", ref, "-p", dest, "--unzip", "-q"],
                           capture_output=True, text=True, env=dict(os.environ), encoding="utf-8")
        for f in glob.glob(os.path.join(dest, "**", "*.csv"), recursive=True)[:4]:
            try:
                if os.path.getsize(f) > 20e6:
                    continue
                df = pd.read_csv(f, low_memory=False)
                for dc in [c for c in df.columns if re.search(r"date|time|day|month|week|period", str(c), re.I)][:2]:
                    dt = pd.to_datetime(df[dc], errors="coerce", format="mixed")
                    if dt.notna().mean() < 0.9 or dt.nunique() != dt.notna().sum():   # need one row per date
                        continue
                    sub = df.assign(_d=dt).dropna(subset=["_d"]).sort_values("_d")
                    for col in [c for c in sub.select_dtypes("number").columns if c != dc][:6]:
                        s = sub[col].dropna()
                        if len(s) >= MIN_POINTS:
                            ds = sub.loc[s.index, "_d"].dt.strftime("%Y-%m-%d").tolist()
                            yield evaluate("kaggle", f"{ref} :: {os.path.basename(f)} :: {col}", ds, s.tolist(),
                                           f"kaggle datasets download {ref}")
                    break
            except Exception as e:
                log(f"  skip {os.path.basename(f)}: {e}")


def diversify(results, per_kind=2):
    """At most `per_kind` results per kind (first 3 words of the title), so eight Treasury
    yields telling the same story don't bury everything else."""
    counts, out = {}, []
    for r in results:
        title = r["name"].split(" - ", 1)[-1] if r["source"] == "fred" else r["name"]
        kind = " ".join(re.findall(r"[A-Za-z]+", title)[:3]).lower()
        if counts.get(kind, 0) < per_kind:
            counts[kind] = counts.get(kind, 0) + 1
            out.append(r)
    return out


def main():
    parser = argparse.ArgumentParser(description="Rank long time series by how much the FSR engine shows")
    parser.add_argument("--only", nargs="+", choices=["fred", "science", "kaggle"], help="limit sources")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--fred-max", type=int, default=250, help="max FRED series to score")
    args = parser.parse_args()
    os.chdir(HERE)
    sources = args.only or ["fred", "science", "kaggle"]

    results = []
    if "science" in sources:
        log("Scanning science feeds...")
        results += [r for r in scan_science() if r]
    if "fred" in sources:
        log("Scanning FRED...")
        results += [r for r in scan_fred(args.fred_max) if r]
    if "kaggle" in sources:
        log("Scanning Kaggle...")
        results += [r for r in scan_kaggle() if r]
    results = diversify(sorted(results, key=lambda r: -r["score"]))

    os.makedirs(OUT, exist_ok=True)
    print(f"\nScored {len(results)} long series. Most chart-worthy for the calculator:\n")
    print(f"{'#':>2}  {'src':<7} {'series':<58} {'pts':>5} {'win':>4} {'normal':>6} {'low':>5} {'now':>5}  shape")
    for i, r in enumerate(results[:args.top], 1):
        print(f"{i:>2}  {r['source']:<7} {r['name'][:58]:<58} {r['points']:>5} {r['window']:>4} "
              f"{r['normal']:>5.0f}% {r['lowest']:>4.0f}% {r['latest']:>4.0f}%  {r['shape']}"
              + (" | at record level" if r["at_extreme"] else ""))
        path = os.path.join(OUT, safe_name(r["name"]) + ".txt")
        with open(path, "w") as f:
            f.write(", ".join(f"{v:g}" for v in r["_values"]))
    print(f"\nSeries saved to {OUT} (one .txt per result, ready to paste). Crack dates for the top 5:")
    for r in results[:5]:
        print(f"  {r['name'][:60]}: {', '.join(r['crack_dates'])}  [{r['command']}]")
    with open(os.path.join(OUT, f"results_{date.today()}.json"), "w") as f:
        json.dump([{k: v for k, v in r.items() if k != "_values"} for r in results], f, indent=1)


if __name__ == "__main__":
    main()
