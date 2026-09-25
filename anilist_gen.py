"""
anilist_gen.py - Predictability Score for anime audiences (AniList)

Scores how *stable* an anime's audience is day to day, using AniList's
per-show daily trend history (free public GraphQL API, no key):
  - watching   = users currently marked "Watching" (closest thing to live viewership)
  - trending   = that day's list activity (hype spikes on episode drops)
  - popularity = total users with the show on their list (cumulative, smooth)
  - score      = average user rating over time

Each trend point also carries the latest aired episode, so you can see
exactly which episode moved the audience.

Run:
    python anilist_gen.py --top                        # what's trending hardest right now
    python anilist_gen.py "Chainsaw Man"               # daily "watching" count
    python anilist_gen.py "Chainsaw Man" --metric trending
    python anilist_gen.py "Chainsaw Man" --days 60 --k 0.5
    python anilist_gen.py "Chainsaw Man" --csv         # also save date,value CSV
"""
import argparse
import csv
import time
from datetime import datetime, timezone

import requests

from fsr import calculate_predictability

API = "https://graphql.anilist.co"

METRICS = {
    "watching": "inProgress",
    "trending": "trending",
    "popularity": "popularity",
    "score": "averageScore",
}

SEARCH_QUERY = """
query ($search: String, $page: Int) {
  Media(search: $search, type: ANIME) {
    id
    title { romaji english }
    status
    episodes
    trends(sort: DATE_DESC, page: $page, perPage: 25) {
      pageInfo { hasNextPage }
      nodes { date trending averageScore popularity inProgress episode }
    }
  }
}
"""

TOP_QUERY = """
query {
  Page(perPage: 10) {
    media(type: ANIME, sort: TRENDING_DESC) {
      title { romaji english }
      trending
      popularity
      status
      nextAiringEpisode { episode }
    }
  }
}
"""


def gql(query: str, variables: dict = None) -> dict:
    for attempt in range(3):
        resp = requests.post(API, json={"query": query, "variables": variables or {}}, timeout=20)
        if resp.status_code == 429:  # AniList rate limit - back off and retry
            time.sleep(int(resp.headers.get("Retry-After", 60)))
            continue
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            raise ValueError(body["errors"][0]["message"])
        return body["data"]
    raise RuntimeError("AniList rate limit hit repeatedly - try again in a minute.")


def show_title(media: dict) -> str:
    return media["title"]["english"] or media["title"]["romaji"]


def fetch_trends(search: str, days: int):
    """Page back through the daily trend history until we have `days` points."""
    nodes, media, page = [], None, 1
    while True:
        data = gql(SEARCH_QUERY, {"search": search, "page": page})
        media = data["Media"]
        if media is None:
            raise ValueError(f"No AniList anime found for '{search}'.")
        trends = media["trends"]
        nodes.extend(trends["nodes"])
        if len(nodes) >= days or not trends["pageInfo"]["hasNextPage"]:
            break
        page += 1
    nodes = sorted(nodes[:days], key=lambda n: n["date"])
    if not nodes:
        raise ValueError(f"AniList has no trend history for '{show_title(media)}'.")
    return media, nodes


def print_top():
    shows = gql(TOP_QUERY)["Page"]["media"]
    print("\nTrending hardest on AniList right now:\n")
    for i, m in enumerate(shows, 1):
        next_ep = m["nextAiringEpisode"]
        airing = f"ep {next_ep['episode'] - 1} out" if next_ep else m["status"].lower()
        print(f"{i:>2}. {show_title(m)}  (trending {m['trending']}, {m['popularity']:,} on lists, {airing})")


def main():
    parser = argparse.ArgumentParser(description="FSR predictability score for an anime's AniList audience")
    parser.add_argument("show", nargs="?", help="Anime title (quote multi-word titles)")
    parser.add_argument("--top", action="store_true", help="list the 10 most-trending anime right now")
    parser.add_argument("--metric", choices=METRICS.keys(), default="watching",
                        help="watching (default), trending, popularity, or score")
    parser.add_argument("--days", type=int, default=90, help="how many recent days of history (default 90)")
    parser.add_argument("--k", type=float, default=1.0,
                        help="k-factor: 0.5=sports (forgiving), 1.0=general, 2.0=finance (strict), 15.0=pharma")
    parser.add_argument("--csv", action="store_true", help="also save the series as <show>_anilist_<metric>.csv")
    args = parser.parse_args()

    if args.top:
        print_top()
        return
    if not args.show:
        parser.error("give a show title, or use --top")

    media, nodes = fetch_trends(args.show, args.days)
    field = METRICS[args.metric]
    points = [n for n in nodes if n[field] is not None]
    for prev, cur in zip(points, points[1:]):  # AniList leaves episode blank on some days - carry it forward
        cur["episode"] = cur["episode"] or prev["episode"]
    series = [p[field] for p in points]
    dates = [datetime.fromtimestamp(p["date"], tz=timezone.utc).strftime("%Y-%m-%d") for p in points]
    score = calculate_predictability(series, args.k)
    title = show_title(media)

    peak_i = series.index(max(series))
    print(f"\nAniList {args.metric} for: {title}  ({media['status'].lower()}, {media['episodes'] or '?'} eps)")
    print(f"Range: {dates[0]} to {dates[-1]}, {len(series)} daily points")
    print(f"Latest: {series[-1]:,}  (episode {points[-1]['episode'] or '-'})")
    print(f"Peak:   {series[peak_i]:,} on {dates[peak_i]}  (episode {points[peak_i]['episode'] or '-'})")
    print(f"\nPredictability Score (k={args.k}): {score:.1f}%")

    # AniList's trend history has occasional holes (Re:ZERO S4 is missing its
    # whole premiere fortnight). A pasted series hides them, so call them out.
    day = [datetime.strptime(dt, "%Y-%m-%d") for dt in dates]
    gaps = [(dates[i - 1], dates[i], (day[i] - day[i - 1]).days - 1)
            for i in range(1, len(day)) if (day[i] - day[i - 1]).days > 1]
    for before, after, missing in gaps:
        print(f"WARNING: {missing} day(s) missing between {before} and {after} - the chart will skip over them")

    # Days where a new episode first shows up - handy for chart callouts / the script.
    drops = [(dates[i], points[i]["episode"]) for i in range(1, len(points))
             if points[i]["episode"] and points[i]["episode"] != points[i - 1]["episode"]]
    if drops:
        print("\nEpisode drops: " + ", ".join(f"ep {ep} {dt}" for dt, ep in drops))

    print("\n--- Series (copy for a chart) ---")
    print(", ".join(map(str, series)))

    if args.csv:
        path = "".join(c if c.isalnum() else "_" for c in title).strip("_").lower() + f"_anilist_{args.metric}.csv"
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", args.metric, "episode"])
            writer.writerows((dt, p[field], p["episode"]) for dt, p in zip(dates, points))
        print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
