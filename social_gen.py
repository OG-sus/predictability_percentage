"""
social_gen.py — Social Media Engagement Generator
==================================================
Fetches or generates social engagement series (comment counts, view counts,
follower growth) and computes the FSR Predictability Score™.

Supported platforms:
  • Reddit  — via PRAW (official Reddit API) with synthetic fallback
  • YouTube — via YouTube Data API v3 (requires YOUTUBE_API_KEY)
  • Twitter/X — synthetic generator (API is paywalled)
  • Generic  — manual data entry or synthetic
"""

import os
import time
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

K_SOCIAL = 0.8  # Social metrics are moderately volatile

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

try:
    from googleapiclient.discovery import build as yt_build
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Reddit — daily comment/post counts via PRAW
# ---------------------------------------------------------------------------

def reddit_daily_counts(subreddit_name, days=14, count_type="comments"):
    """
    Fetch daily comment or post counts for a subreddit using PRAW.
    Requires env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT.
    Falls back to synthetic data if credentials are missing.
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "fsr-social-gen/1.0")

    if PRAW_AVAILABLE and client_id and client_secret:
        try:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            sub = reddit.subreddit(subreddit_name)
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            counts = {}
            stream = sub.comments(limit=1000) if count_type == "comments" else sub.new(limit=1000)
            for item in stream:
                created = datetime.fromtimestamp(item.created_utc, tz=timezone.utc)
                if created < cutoff:
                    break
                day = created.date().isoformat()
                counts[day] = counts.get(day, 0) + 1
                time.sleep(0.01)

            dates = sorted(counts.keys())[-days:]
            series = [counts.get(d, 0) for d in dates]
            if series:
                label = f"r/{subreddit_name} ({count_type}/day)"
                return _run_analysis(label, series, unit=f"{count_type}/day")
        except Exception as e:
            print(f"  [PRAW] Error: {e} — using synthetic fallback.")

    print(f"  [Reddit] API unavailable — generating synthetic engagement for r/{subreddit_name}")
    series = synthetic_engagement_series(n=days, base=500, label=f"r/{subreddit_name}")
    return _run_analysis(f"r/{subreddit_name} (synthetic {count_type}/day)", series)


# ---------------------------------------------------------------------------
# YouTube — daily view counts via Data API v3
# ---------------------------------------------------------------------------

def youtube_channel_views(channel_id, days=14):
    """
    Fetch daily view counts for a YouTube channel.
    Requires env var: YOUTUBE_API_KEY
    Falls back to synthetic data if key is missing.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("  [YouTube] YOUTUBE_API_KEY not set — using synthetic fallback.")
        series = synthetic_engagement_series(n=days, base=50000, spike_chance=0.1)
        return _run_analysis(f"YouTube Channel (synthetic, {days}d)", series, unit="views/day")

    if not YOUTUBE_AVAILABLE:
        print("  [YouTube] google-api-python-client not installed. Run: pip install google-api-python-client")
        series = synthetic_engagement_series(n=days, base=50000)
        return _run_analysis(f"YouTube Channel (synthetic, {days}d)", series, unit="views/day")

    try:
        yt = yt_build("youtube", "v3", developerKey=api_key)
        published_after = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
        req = yt.search().list(
            part="snippet",
            channelId=channel_id,
            type="video",
            publishedAfter=published_after,
            maxResults=50,
            order="date",
        )
        result = req.execute()
        video_ids = [item["id"]["videoId"] for item in result.get("items", [])]
        if not video_ids:
            print("No videos found in that time window.")
            return None

        stats_req = yt.videos().list(part="statistics,snippet", id=",".join(video_ids))
        stats_result = stats_req.execute()

        daily = {}
        for item in stats_result.get("items", []):
            pub_date = item["snippet"]["publishedAt"][:10]
            views = int(item["statistics"].get("viewCount", 0))
            daily[pub_date] = daily.get(pub_date, 0) + views

        dates = sorted(daily.keys())
        series = [daily[d] for d in dates]
        return _run_analysis(f"YouTube {channel_id} ({days}d)", series, unit="views/day")

    except Exception as e:
        print(f"  [YouTube] Error: {e}")
        return None


# ---------------------------------------------------------------------------
# Twitter/X — synthetic only (API is paywalled)
# ---------------------------------------------------------------------------

def twitter_synthetic_engagement(handle, n=30, base_impressions=10000, seed=None):
    """
    Generate synthetic Twitter/X daily impression series.
    (Official API requires paid access — this provides realistic synthetic data.)
    """
    series = synthetic_engagement_series(n=n, base=base_impressions, seed=seed, spike_chance=0.1)
    return _run_analysis(f"@{handle} impressions (synthetic, {n}d)", series, unit="impressions/day")


# ---------------------------------------------------------------------------
# Generic / synthetic helpers
# ---------------------------------------------------------------------------

def synthetic_engagement_series(n=30, base=1000, spike_chance=0.12, volatility=0.3, seed=None, label=""):
    """Generate realistic social engagement series with random viral spikes."""
    rng = np.random.default_rng(seed)
    series = []
    current = float(base)
    for _ in range(n):
        drift = rng.normal(0, volatility * current)
        current = max(10, current + drift)
        if rng.random() < spike_chance:
            current *= rng.uniform(2.5, 6.0)
        series.append(int(round(current)))
        # Decay spike back toward base gradually
        current = current * 0.7 + base * 0.3
    return series


def follower_growth_series(n=30, start=10000, daily_gain=150, volatility=100, seed=None):
    """Generate a cumulative follower count series."""
    rng = np.random.default_rng(seed)
    counts = [start]
    for _ in range(n - 1):
        gain = max(0, int(rng.normal(daily_gain, volatility)))
        counts.append(counts[-1] + gain)
    return counts


# ---------------------------------------------------------------------------
# Shared display + chart
# ---------------------------------------------------------------------------

def _run_analysis(label, series, unit=""):
    if not series or len(series) < 2:
        print("Not enough data points.")
        return None

    score = calculate_predictability(series, k=K_SOCIAL)
    avg = sum(series) / len(series)

    output = ", ".join(map(str, series))
    print(f"\n{label} ({len(series)} points)")
    print(f"\n--- COPY DATA ---\n{output}\n")
    print(f"Predictability Score : {score:.2f}")
    print(f"Average              : {avg:.1f}" + (f" {unit}" if unit else ""))

    _save_chart(label, series, unit)
    return score


def _save_chart(label, series, unit=""):
    window_size = min(10, len(series) // 2)
    if window_size < 2:
        return
    results = calculate_sliding_window(series, window_size, k=K_SOCIAL)
    scores = [None] * (window_size - 1) + [r['score'] for r in results]
    avg = sum(series) / len(series)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(series, marker='o', linestyle='-', color='#e91e63', alpha=0.8, label=unit or "Engagement")
    ax1.axhline(y=avg, color='gray', linestyle='--', label=f'Avg ({avg:.0f})')
    ax1.set_title(label)
    ax1.set_ylabel(unit or "Count")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(scores, color='#673ab7', linewidth=2, label=f'Predictability ({window_size}-pt window)')
    ax2.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
    ax2.axhline(y=60, color='orange', linestyle='--', label='Volatile')
    ax2.set_title("Engagement Stability")
    ax2.set_ylabel("Score (0-100)")
    ax2.set_xlabel("Day")
    ax2.set_ylim(0, 105)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    out_dir = os.path.join("static", "images", "social_charts")
    os.makedirs(out_dir, exist_ok=True)
    safe = label.replace(" ", "_").replace("/", "_")[:40]
    path = os.path.join(out_dir, f"{safe}_analysis.png")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Chart saved → {path}")


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Social Media Predictability Generator")
    print("======================================")
    print("Modes:")
    print("  1. Reddit     — daily comment/post counts (PRAW API or synthetic)")
    print("  2. YouTube    — daily views (YouTube Data API or synthetic)")
    print("  3. Twitter/X  — synthetic daily impressions")
    print("  4. Follower growth series (synthetic)")
    print()

    while True:
        mode = input("Select mode (1-4) or 'q' to quit: ").strip()
        if mode.lower() == 'q':
            break

        if mode == '1':
            sub = input("Subreddit name (no r/, e.g. 'leagueoflegends'): ").strip()
            days = int(input("Days to analyze (default 14): ").strip() or "14")
            ctype = input("Count type — comments or posts (default comments): ").strip() or "comments"
            reddit_daily_counts(sub, days=days, count_type=ctype)

        elif mode == '2':
            channel_id = input("YouTube Channel ID (e.g. UC...): ").strip()
            days = int(input("Days (default 14): ").strip() or "14")
            youtube_channel_views(channel_id, days=days)

        elif mode == '3':
            handle = input("Twitter/X handle (no @): ").strip() or "brand"
            n = int(input("Days (default 30): ").strip() or "30")
            base = int(input("Base daily impressions (default 10000): ").strip() or "10000")
            twitter_synthetic_engagement(handle, n=n, base_impressions=base)

        elif mode == '4':
            label = input("Account/brand name: ").strip() or "Account"
            n = int(input("Days (default 30): ").strip() or "30")
            start = int(input("Starting follower count (default 10000): ").strip() or "10000")
            gain = int(input("Expected daily gain (default 150): ").strip() or "150")
            series = follower_growth_series(n=n, start=start, daily_gain=gain)
            _run_analysis(f"{label} Follower Growth", series, unit="followers")

        else:
            print("Invalid choice.")