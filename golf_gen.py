import os
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

K_GOLF = 2.0  # Strict k-factor — golf rewards consistency


# ---------------------------------------------------------------------------
# Web scraping: ESPN Golf leaderboard / player scoring history
# ---------------------------------------------------------------------------

def fetch_player_rounds_espn(player_name):
    """
    Scrape recent round scores for a PGA Tour player from ESPN.
    Returns list of round totals (ints). Falls back to None on failure.
    """
    print(f"  [ESPN] Fetching round scores for {player_name}...")
    search_name = player_name.lower().replace(" ", "+")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
    }
    try:
        # ESPN golf scorecards search
        url = f"https://www.espn.com/golf/player/scorecards/_/id/search/{search_name}"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        tables = pd.read_html(StringIO(resp.text))
        for table in tables:
            # Look for a table with numeric score columns
            numeric_cols = table.select_dtypes(include="number").columns.tolist()
            if numeric_cols:
                scores = table[numeric_cols[0]].dropna().astype(int).tolist()
                if len(scores) >= 4:
                    return scores[:20]  # cap at 20 rounds
        return None
    except Exception as e:
        print(f"  [ESPN] Scrape failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Synthetic round generator
# ---------------------------------------------------------------------------

def synthetic_rounds(n=20, avg_score=72, spread=4, seed=None):
    """
    Generate synthetic 18-hole round totals. avg_score is par-relative starting point.
    spread controls how consistent the player is.
    """
    rng = np.random.default_rng(seed)
    rounds = np.round(rng.normal(avg_score, spread, size=n)).astype(int)
    return np.clip(rounds, avg_score - 15, avg_score + 20).tolist()


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_round_scores(player_name, round_scores):
    """Run FSR analysis on a list of 18-hole totals. Prints and saves chart."""
    if not round_scores or len(round_scores) < 2:
        print("Need at least 2 rounds.")
        return None

    score = calculate_predictability(round_scores, k=K_GOLF)
    avg = sum(round_scores) / len(round_scores)

    output = ", ".join(map(str, round_scores))
    print(f"\n--- {player_name} ---")
    print(f"Rounds ({len(round_scores)}): {output}")
    print(f"\nPredictability Score : {score:.2f}")
    print(f"Scoring Average      : {avg:.1f}")
    print(f"\n--- COPY DATA ---\n{output}\n")

    _save_chart(player_name, round_scores, avg)
    return score


def _save_chart(name, series, avg):
    window_size = min(10, len(series) // 2)
    if window_size < 2:
        return
    results = calculate_sliding_window(series, window_size, k=K_GOLF)
    scores = [None] * (window_size - 1) + [r['score'] for r in results]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(series, marker='o', linestyle='-', color='#2e7d32', alpha=0.8, label='Round Score')
    ax1.axhline(y=avg, color='gray', linestyle='--', label=f'Avg ({avg:.1f})')
    ax1.invert_yaxis()  # lower scores = better in golf
    ax1.set_title(f"{name} — Round Scores (lower = better)")
    ax1.set_ylabel("Score")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(scores, color='#c8102e', linewidth=2, label=f'Predictability ({window_size}-round window)')
    ax2.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
    ax2.axhline(y=60, color='orange', linestyle='--', label='Volatile')
    ax2.set_title("Scoring Consistency")
    ax2.set_ylabel("Score (0-100)")
    ax2.set_xlabel("Round #")
    ax2.set_ylim(0, 105)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    out_dir = os.path.join("static", "images", "golf_charts")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{name.replace(' ', '_')}_golf_analysis.png"
    path = os.path.join(out_dir, fname)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Chart saved → {path}")


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Golf Predictability Generator")
    print("=============================")
    print("Modes:")
    print("  1. Fetch real rounds from ESPN (web scrape)")
    print("  2. Enter round scores manually")
    print("  3. Generate synthetic rounds")
    print()

    while True:
        mode = input("Select mode (1-3) or 'q' to quit: ").strip()
        if mode.lower() == 'q':
            break

        if mode == '1':
            player_name = input("Player name (e.g. 'Scottie Scheffler'): ").strip()
            rounds = fetch_player_rounds_espn(player_name)
            if rounds:
                analyze_round_scores(player_name, rounds)
            else:
                print("Could not fetch data. Try mode 2 (manual) or 3 (synthetic).")

        elif mode == '2':
            player_name = input("Player/label name: ").strip() or "Golfer"
            raw = input("Enter round scores (comma-separated, e.g. 70,68,72,71): ").strip()
            try:
                rounds = [int(x.strip()) for x in raw.split(",") if x.strip()]
                analyze_round_scores(player_name, rounds)
            except ValueError:
                print("Invalid input — use integers separated by commas.")

        elif mode == '3':
            player_name = input("Player/label name: ").strip() or "Synthetic Golfer"
            n = int(input("Number of rounds (default 20): ").strip() or "20")
            avg = float(input("Average score (default 72): ").strip() or "72")
            spread = float(input("Consistency spread (default 4): ").strip() or "4")
            rounds = synthetic_rounds(n=n, avg_score=int(avg), spread=spread)
            analyze_round_scores(player_name, rounds)

        else:
            print("Invalid choice.")