"""
ai_outage_gen.py - FSR on an AI service's reliability, from its full public status history

Pulls every incident ever posted on a Statuspage status site (Anthropic/Claude by default,
history back to Feb 2023) and builds weekly series fed straight into the FSR engine:
  minutes   - minutes per week with at least one incident open (overlaps merged, so two
              incidents at once count once; incidents spanning weeks are split across them)
  incidents - number of incidents started per week

Caveat for scripts: these are *posted* incidents. "Degraded performance" counts the same
as a full outage unless you filter with --impact, and a status page that posts more
often looks worse than one that posts less - it measures what the company reports.

Run:
    python ai_outage_gen.py                                # Anthropic, weekly outage minutes
    python ai_outage_gen.py --series incidents
    python ai_outage_gen.py --impact major                 # only major/critical incidents
    python ai_outage_gen.py --site www.githubstatus.com    # any Statuspage-hosted site
"""
import argparse
import os
import re
import statistics
from datetime import datetime, timedelta, timezone

import requests

from fsr import calculate_predictability

HERE = os.path.dirname(os.path.abspath(__file__))
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
RANK = {"none": 0, "minor": 1, "major": 2, "critical": 3}
# "Jul 31, 06:18 - 07:04 UTC"  or  "Aug 14, 23:57 - Aug 15, 00:27 UTC"
STAMP = re.compile(r"(\w{3}) (\d+), (\d\d):(\d\d) - (?:(\w{3}) (\d+), )?(\d\d):(\d\d) UTC")


def fetch_incidents(site):
    """[(start, end, impact, name)] for every incident in the site's history, oldest first."""
    out, page = [], 1
    while True:
        body = requests.get(f"https://{site}/history.json", params={"page": page}, timeout=30).json()
        months = body["months"]
        created = body.get("page_status", {}).get("page", {}).get("created_at", "")[:7]   # e.g. "2023-01"
        incidents = [(m["year"], i) for m in months for i in m["incidents"]]
        if not months:
            break
        for year, inc in incidents:
            m = STAMP.search(re.sub(r"<[^>]+>", "", inc["timestamp"]))
            if not m:
                continue
            mon, day, h1, m1, mon2, day2, h2, m2 = m.groups()
            start = datetime(year, MONTHS[mon], int(day), int(h1), int(m1), tzinfo=timezone.utc)
            end = datetime(year, MONTHS[mon2 or mon], int(day2 or day), int(h2), int(m2), tzinfo=timezone.utc)
            if end < start:                       # crossed New Year (Dec 31 -> Jan 1)
                end = end.replace(year=year + 1)
            out.append((start, end, inc.get("impact", "none"), inc["name"]))
        oldest = min((f"{m['year']}-{list(MONTHS).index(m['name'][:3]) + 1:02d}" for m in months), default="")
        if created and oldest <= created:         # reached the month the status page was created
            break
        page += 1
        if page > 60:                             # safety: 60 pages = 15 years of history
            break
    return sorted(out)


def weekly(incidents, since):
    """(week_labels, minutes_open_per_week, incidents_started_per_week) on full Monday-Sunday UTC weeks."""
    start = since - timedelta(days=since.weekday())
    now = datetime.now(timezone.utc)
    last = now - timedelta(days=now.weekday()) - timedelta(days=7)     # last complete week
    weeks = []
    w = start
    while w <= last:
        weeks.append(w)
        w += timedelta(days=7)
    # merge overlapping incident windows so simultaneous incidents count once
    merged = []
    for s, e, _, _ in incidents:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    minutes = [0.0] * len(weeks)
    counts = [0] * len(weeks)
    for i, w in enumerate(weeks):
        we = w + timedelta(days=7)
        for s, e in merged:
            overlap = (min(e, we) - max(s, w)).total_seconds() / 60
            if overlap > 0:
                minutes[i] += overlap
        counts[i] = sum(1 for s, _, _, _ in incidents if w <= s < we)
    return [str(w.date()) for w in weeks], minutes, counts


def main():
    parser = argparse.ArgumentParser(description="FSR on an AI service's public outage history")
    parser.add_argument("--site", default="status.anthropic.com", help="Statuspage host (default Anthropic)")
    parser.add_argument("--series", choices=["minutes", "incidents"], default="minutes")
    parser.add_argument("--impact", choices=["minor", "major", "critical"], help="only incidents at least this severe")
    parser.add_argument("--since", default="2023-03-06", help="first week (YYYY-MM-DD)")
    parser.add_argument("--window", type=int, default=12, help="sliding window in weeks (default 12)")
    parser.add_argument("--k", type=float, default=1.0)
    args = parser.parse_args()

    inc = fetch_incidents(args.site)
    if args.impact:
        inc = [x for x in inc if RANK.get(x[2], 0) >= RANK[args.impact]]
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    labels, minutes, counts = weekly([x for x in inc if x[1] >= since], since)
    v = minutes if args.series == "minutes" else counts
    unit = "minutes with an incident open" if args.series == "minutes" else "incidents started"

    print(f"\n{args.site}: {len(inc)} incidents{' (' + args.impact + '+)' if args.impact else ''}, "
          f"{len(v)} full weeks ({labels[0]} to {labels[-1]})")
    longest = max(inc, key=lambda x: x[1] - x[0])
    print(f"Longest incident: {(longest[1] - longest[0]).total_seconds() / 3600:.0f} h - '{longest[3][:60]}' ({longest[0]:%Y-%m-%d})")
    hi = v.index(max(v))
    print(f"Weekly {unit}: median {statistics.median(v):,.0f}, worst {max(v):,.0f} (week of {labels[hi]}), "
          f"latest {v[-1]:,.0f}")
    zero = sum(1 for x in v if x == 0) / len(v)
    if zero > 0.2:
        print(f"WARNING: {zero:.0%} of weeks are zero - FSR readings will be noisy. Try a later --since.")
    print(f"FSR (k={args.k}): {calculate_predictability(v, args.k):.1f}%")
    r = [calculate_predictability(v[i - args.window:i], args.k) for i in range(args.window, len(v) + 1)]
    lows = sorted(range(len(r)), key=r.__getitem__)[:3]
    print(f"{args.window}-week window: typical {statistics.median(r):.1f}%, latest {r[-1]:.1f}%, lowest "
          + ", ".join(f"{r[i]:.1f}% (week of {labels[i + args.window - 1]})" for i in lows))

    slug = args.site.replace("status.", "").split(".")[0] + f"_{args.series}" + (f"_{args.impact}" if args.impact else "")
    path = os.path.join(HERE, "output", f"ai_outage_{slug}_weekly.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(", ".join(f"{x:g}" for x in v))
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
