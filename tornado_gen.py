"""
tornado_gen.py - FSR on U.S. tornado counts (NOAA Storm Prediction Center, free, no key)

Two sources stitched together:
  - SPC's final tornado database: every confirmed U.S. tornado since 1950 (through last year)
  - SPC's daily preliminary storm reports for this year (raw reports - they run ~10-20% high
    because one tornado can be reported more than once; SPC trims them later)

Monthly counts never hit zero nationally, so they chart cleanly: every spring is a spike, and
outbreaks (April 2011, the 2024 run) stick out. Daily counts are mostly zeros - don't chart those.

Run:
    python tornado_gen.py                    # U.S. monthly since 1950
    python tornado_gen.py --since 2000
    python tornado_gen.py --state FL         # one state (many zero months - the tool warns)
    python tornado_gen.py --days 2026-10-08 2026-10-12   # list this year's reports for an outbreak
"""
import argparse
import csv
import io
import os
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "predictability-api.com research"}
FINAL = "https://www.spc.noaa.gov/wcm/data/1950-{y}_actual_tornadoes.csv"
DAILY = "https://www.spc.noaa.gov/climo/reports/{d:%y%m%d}_rpts_torn.csv"


def final_db():
    """Newest SPC final database available (it's published a few months after each year ends)."""
    for y in range(date.today().year - 1, date.today().year - 4, -1):
        r = requests.get(FINAL.format(y=y), headers=UA, timeout=120)
        if r.ok and r.text.startswith("om"):
            return y, list(csv.DictReader(io.StringIO(r.text)))
    raise SystemExit("Couldn't download SPC's final tornado database.")


def daily_reports(day):
    """This year's preliminary tornado reports for one day (SPC's day runs 12Z to 12Z)."""
    r = requests.get(DAILY.format(d=day), headers=UA, timeout=60)
    if not r.ok:
        return day, []
    return day, [row for row in csv.DictReader(io.StringIO(r.text)) if row.get("State")]


def main():
    p = argparse.ArgumentParser(description="FSR on U.S. tornado counts")
    p.add_argument("--since", type=int, default=1950)
    p.add_argument("--state", type=str.upper, help="two-letter state (default: whole U.S.)")
    p.add_argument("--window", type=int, default=12, help="months (default 12)")
    p.add_argument("--k", type=float, default=1.0)
    p.add_argument("--days", nargs=2, metavar=("START", "END"), help="list preliminary reports between two dates")
    a = p.parse_args()

    if a.days:
        d0, d1 = date.fromisoformat(a.days[0]), date.fromisoformat(a.days[1])
        days = [d0 + timedelta(n) for n in range((d1 - d0).days + 1)]
        with ThreadPoolExecutor(8) as ex:
            for day, rows in ex.map(daily_reports, days):
                states = sorted({r["State"] for r in rows})
                print(f"{day}: {len(rows):>3} tornado reports  {' '.join(states)}")
        return

    last_final, rows = final_db()
    counts = {}
    for r in rows:
        if r["sg"] not in ("1", "-9"):  # sg=2 rows are state segments of a tornado already counted
            continue
        if a.state and r["st"] != a.state:
            continue
        key = (int(r["yr"]), int(r["mo"]))
        counts[key] = counts.get(key, 0) + 1

    # Preliminary reports for every year after the final database, through yesterday.
    prelim_from = date(last_final + 1, 1, 1)
    days = [prelim_from + timedelta(n) for n in range((date.today() - prelim_from).days)]
    print(f"Final SPC database through {last_final}; adding {len(days)} days of preliminary reports...")
    with ThreadPoolExecutor(16) as ex:
        for day, reps in ex.map(daily_reports, days):
            n = sum(1 for r in reps if not a.state or r["State"] == a.state)
            counts[(day.year, day.month)] = counts.get((day.year, day.month), 0) + n

    months, v = [], []
    y, m = a.since, 1
    today = date.today()
    while (y, m) <= (today.year, today.month):
        months.append(f"{y}-{m:02d}")
        v.append(counts.get((y, m), 0))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    where = a.state or "U.S."
    hi = v.index(max(v))
    print(f"\n{where} tornadoes per month: {len(v)} months, {months[0]} to {months[-1]} "
          f"(this month is partial; {last_final + 1}+ are preliminary reports)")
    print(f"Typical {statistics.median(v):g} | record {v[hi]} ({months[hi]}) | latest {v[-1]} | "
          f"same month last year {v[-13]}")
    same = sorted(((v[i], months[i]) for i in range(len(v) - 1) if months[i][5:] == months[-1][5:]), reverse=True)
    print(f"Biggest {months[-1][5:]}s on record: " + ", ".join(f"{mo} ({c})" for c, mo in same[:5]))
    zeros = sum(1 for x in v if x == 0)
    if zeros > len(v) * 0.03:
        print(f"WARNING: {zeros} zero months - FSR breaks near zero. Use the whole U.S. or a later --since.")
    r = [calculate_predictability(v[i - a.window:i], a.k) for i in range(a.window, len(v) + 1)]
    e = months[a.window - 1:]
    print(f"FSR (k={a.k}) overall {calculate_predictability(v, a.k):.2f}% | {a.window}-month window: typical "
          f"{statistics.median(r):.1f}%, lowest {min(r):.1f}% ({e[r.index(min(r))]}), latest {r[-1]:.1f}%")
    slug = (a.state or "us").lower()
    path = os.path.join(HERE, "output", f"tornadoes_{slug}_monthly_since{a.since}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(str(x) for x in v))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
