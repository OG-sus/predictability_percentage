"""
pageviews_gen.py - Predictability Score for Wikipedia pageviews

Scores how *stable* public attention is for any show, person, game, or
topic, using daily English Wikipedia pageviews (Wikimedia REST API, free,
no key, history back to mid-2015). Unlike Google Trends these are raw
view counts, not a 0-100 scale, so two separately-run articles ARE
directly comparable.

Run:
    python pageviews_gen.py "Stranger Things"
    python pageviews_gen.py "Stranger Things" --days 365
    python pageviews_gen.py "Stranger Things" --weekly        # weekly totals, smooths weekday noise
    python pageviews_gen.py "One Piece" --compare "Naruto"
    python pageviews_gen.py "Stranger Things" --csv           # also save date,views CSV
"""
import argparse
import csv
from datetime import date, timedelta
from urllib.parse import quote

import requests

from fsr import calculate_predictability

# Wikimedia requires a descriptive User-Agent or it rejects the request.
HEADERS = {"User-Agent": "predictability-api.com FSR pageviews script (predictabilitycalculator@gmail.com)"}
PAGEVIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
             "en.wikipedia/all-access/user/{article}/daily/{start}/{end}")


def resolve_title(term: str) -> str:
    """Follow Wikipedia redirects so 'GTA 6' lands on the real article title."""
    resp = requests.get("https://en.wikipedia.org/w/api.php", headers=HEADERS, timeout=20, params={
        "action": "query", "titles": term, "redirects": 1, "format": "json"})
    resp.raise_for_status()
    page = next(iter(resp.json()["query"]["pages"].values()))
    if "missing" in page:
        raise ValueError(f"No Wikipedia article titled '{term}' - check the exact article name.")
    return page["title"]


def fetch_views(term: str, days: int, weekly: bool):
    title = resolve_title(term)
    end = date.today() - timedelta(days=1)  # today's counts aren't complete yet
    start = end - timedelta(days=days - 1)
    url = PAGEVIEWS.format(article=quote(title.replace(" ", "_"), safe=""),
                           start=start.strftime("%Y%m%d00"), end=end.strftime("%Y%m%d00"))
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code == 404:
        raise ValueError(f"No pageview data for '{title}' in that range.")
    resp.raise_for_status()
    items = resp.json()["items"]
    dates = [f"{i['timestamp'][:4]}-{i['timestamp'][4:6]}-{i['timestamp'][6:8]}" for i in items]
    views = [i["views"] for i in items]
    if weekly:
        # Anchor weeks to the most recent day and drop the leftover partial
        # week at the start, so no bucket is an undercounted 3-day "week".
        start = len(views) % 7
        dates = dates[start::7]
        views = [sum(views[i:i + 7]) for i in range(start, len(views), 7)]
    return title, dates, views


def summarize(title, dates, views, k):
    score = calculate_predictability(views, k)
    peak_i = views.index(max(views))
    print(f"{title}: avg {sum(views) / len(views):,.0f}, peak {views[peak_i]:,} on {dates[peak_i]}, "
          f"latest {views[-1]:,}, Predictability Score (k={k}): {score:.1f}%")


def save_csv(title, dates, views):
    path = "".join(c if c.isalnum() else "_" for c in title).strip("_").lower() + "_pageviews.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "views"])
        writer.writerows(zip(dates, views))
    print(f"Saved {path}")


def main():
    parser = argparse.ArgumentParser(description="FSR predictability score for Wikipedia pageviews")
    parser.add_argument("article", help="Wikipedia article (show, person, game, topic) - quote multi-word titles")
    parser.add_argument("--days", type=int, default=90, help="how many recent days (default 90, max back to 2015)")
    parser.add_argument("--weekly", action="store_true", help="sum into weekly totals (smooths weekday noise)")
    parser.add_argument("--k", type=float, default=1.0,
                        help="k-factor: 0.5=sports (forgiving), 1.0=general, 2.0=finance (strict), 15.0=pharma")
    parser.add_argument("--compare", metavar="ARTICLE2", default=None, help="score a second article alongside it")
    parser.add_argument("--csv", action="store_true", help="also save the series as <article>_pageviews.csv")
    args = parser.parse_args()

    runs = [fetch_views(args.article, args.days, args.weekly)]
    if args.compare:
        runs.append(fetch_views(args.compare, args.days, args.weekly))

    step = "weekly" if args.weekly else "daily"
    print(f"\nWikipedia pageviews, {runs[0][1][0]} to {runs[0][1][-1]} ({len(runs[0][2])} {step} points)\n")
    for title, dates, views in runs:
        summarize(title, dates, views, args.k)
    if args.compare:
        more = max(runs, key=lambda r: sum(r[2]))[0]
        print(f"\nActually more viewed: {more}")

    print("\n--- Series (copy for charts) ---")
    for title, dates, views in runs:
        print(f"{title}: " + ", ".join(map(str, views)))
        if args.csv:
            save_csv(title, dates, views)


if __name__ == "__main__":
    main()
