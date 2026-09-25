"""
search_hype_gen.py - Predictability Score for Google search interest

Scores how *stable* public search interest is for any person or topic -
good fodder for the "novelty" content angle: apply the same
"institutional-grade" methodology to something silly or relatable
instead of another finance chart.

Uses pytrends (unofficial Google Trends client, no API key) for the
search-interest series, then the project's own calculate_predictability().

Run:
    python search_hype_gen.py "Taylor Swift"
    python search_hype_gen.py "Taylor Swift" --window recent   # last 7 days, hourly - more reactive
    python search_hype_gen.py "Taylor Swift" --k 0.5            # more forgiving of swings

    # Compare two terms on a SHARED 0-100 scale. Important: Google Trends
    # normalizes each solo query to its own peak, so two separately-run
    # terms are NOT comparable in magnitude - a barely-searched term can
    # look bigger than a heavily-searched one just because its own peak
    # anchors its own scale. --compare fixes that by fetching both terms
    # in one request, so 100 means the same thing for both.
    python search_hype_gen.py "Grand Theft Auto VI" --compare "GTA 6"
"""
import argparse

from pytrends.request import TrendReq

from fsr import calculate_predictability

WINDOWS = {
    "broad": "today 3-m",   # ~90 days, daily resolution - overall trend
    "recent": "now 7-d",    # last 7 days, hourly resolution - catches a single viral moment
}


def fetch_search_series(term: str, window: str):
    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload([term], timeframe=WINDOWS[window])
    df = pytrends.interest_over_time()
    if df.empty:
        raise ValueError(f"No Google Trends data for '{term}' - try a more common spelling/term.")
    return df[term].tolist(), df.index


def fetch_compare_series(term_a: str, term_b: str, window: str):
    pytrends = TrendReq(hl="en-US", tz=360)
    pytrends.build_payload([term_a, term_b], timeframe=WINDOWS[window])
    df = pytrends.interest_over_time()
    if df.empty:
        raise ValueError(f"No Google Trends data for '{term_a}' / '{term_b}' - try more common spellings/terms.")
    return df[term_a].tolist(), df[term_b].tolist()


def main():
    parser = argparse.ArgumentParser(description="FSR predictability score for Google search interest")
    parser.add_argument("term", help="Person, topic, or thing to search interest for (quote multi-word terms)")
    parser.add_argument("--window", choices=WINDOWS.keys(), default="broad",
                         help="broad = ~90 days daily (overall trend), recent = last 7 days hourly (catches a spike)")
    parser.add_argument("--k", type=float, default=1.0,
                         help="k-factor: 0.5=sports (forgiving), 1.0=general, 2.0=finance (strict), 15.0=pharma")
    parser.add_argument("--compare", metavar="TERM2", default=None,
                         help="compare against a second term on a shared scale (fixes misleading solo normalization)")
    args = parser.parse_args()

    if args.compare:
        series_a, series_b = fetch_compare_series(args.term, args.compare, args.window)
        score_a = calculate_predictability(series_a, args.k)
        score_b = calculate_predictability(series_b, args.k)
        avg_a = sum(series_a) / len(series_a)
        avg_b = sum(series_b) / len(series_b)
        winner = args.term if avg_a > avg_b else args.compare

        print(f"\nComparing on a shared scale: '{args.term}' vs '{args.compare}'")
        print(f"Window: {args.window} ({WINDOWS[args.window]}), {len(series_a)} data points\n")
        print(f"{args.term}: avg {avg_a:.1f}/100, peak {max(series_a)}, Predictability Score (k={args.k}): {score_a:.1f}%")
        print(f"{args.compare}: avg {avg_b:.1f}/100, peak {max(series_b)}, Predictability Score (k={args.k}): {score_b:.1f}%")
        print(f"\nActually more searched: {winner}")
        print("\n--- Series (copy for charts) ---")
        print(f"{args.term}: " + ", ".join(map(str, series_a)))
        print(f"{args.compare}: " + ", ".join(map(str, series_b)))
        return

    series, dates = fetch_search_series(args.term, args.window)
    score = calculate_predictability(series, args.k)

    print(f"\nSearch interest for: {args.term}")
    print(f"Window: {args.window} ({WINDOWS[args.window]}), {len(series)} data points")
    print(f"Latest interest: {series[-1]} / 100")
    print(f"Peak interest:   {max(series)} / 100")
    print(f"\nPredictability Score (k={args.k}): {score:.1f}%")
    print("\n--- Series (copy for a chart) ---")
    print(", ".join(map(str, series)))


if __name__ == "__main__":
    main()
