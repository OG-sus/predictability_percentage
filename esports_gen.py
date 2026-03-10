import os
import requests
import re
import numpy as np
import matplotlib.pyplot as plt
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

K_ESPORTS = 0.6  # Forgiving k-factor — esports is naturally volatile


# ---------------------------------------------------------------------------
# Twitch viewer count fetcher (requires env vars or falls back to synthetic)
# ---------------------------------------------------------------------------

def twitch_search_viewers(term="Capcom Cup"):
    """Fetch live viewer counts for a Twitch search term. Returns list of ints."""
    client_id = os.getenv("TWITCH_CLIENT_ID")
    token = os.getenv("TWITCH_OAUTH_TOKEN")
    if client_id and token:
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        r = requests.get(
            f"https://api.twitch.tv/helix/search/channels?query={term}",
            headers=headers, timeout=10
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            viewers = [int(d.get("viewer_count") or 0) for d in data if d.get("is_live")]
            if viewers:
                return viewers
    print("  [Twitch] API unavailable or no live streams found — using synthetic fallback.")
    return synthetic_viewer_spike(n=20, base=5000, spike_chance=0.2)


# ---------------------------------------------------------------------------
# Esports-specific stat generators
# ---------------------------------------------------------------------------

def kd_ratio_series(n=20, base_kd=1.2, volatility=0.4, seed=None):
    """Generate a synthetic K/D ratio series for a player over n matches."""
    rng = np.random.default_rng(seed)
    kd = np.clip(rng.normal(base_kd, volatility, size=n), 0.1, 10.0)
    return [round(float(v), 2) for v in kd]


def win_rate_series(n=30, base_rate=0.55, volatility=0.15, seed=None):
    """Generate a rolling win-rate series (as a fraction 0-1) over n windows."""
    rng = np.random.default_rng(seed)
    rates = np.clip(rng.normal(base_rate, volatility, size=n), 0.0, 1.0)
    return [round(float(v), 3) for v in rates]


def tournament_placements(n=12, avg_place=4, spread=3, seed=None):
    """Generate tournament placement series (lower = better)."""
    rng = np.random.default_rng(seed)
    places = np.clip(np.round(rng.normal(avg_place, spread, size=n)), 1, 32).astype(int)
    return places.tolist()


def synthetic_viewer_spike(n=30, base=10000, spike_chance=0.15, seed=None):
    """Synthetic Twitch-style viewer series with random viral spikes."""
    rng = np.random.default_rng(seed)
    series = []
    for _ in range(n):
        if rng.random() < spike_chance:
            series.append(int(rng.integers(base * 3, base * 8)))
        else:
            series.append(int(rng.integers(int(base * 0.5), int(base * 1.5))))
    return series


# ---------------------------------------------------------------------------
# Display + chart helpers
# ---------------------------------------------------------------------------

def _print_series(name, series, unit=""):
    if not series:
        print("No data.")
        return
    score = calculate_predictability(series, k=K_ESPORTS)
    avg = sum(series) / len(series)
    print(f"\n{name} ({len(series)} points)")
    print(", ".join(map(str, series)))
    print(f"\nPredictability Score : {score:.2f}")
    print(f"Average              : {avg:.2f}{unit}")
    return score


def _save_chart(name, series, label, unit="", filename=None):
    window_size = min(10, len(series) // 2)
    if window_size < 2:
        return
    results = calculate_sliding_window(series, window_size, k=K_ESPORTS)
    scores = [None] * (window_size - 1) + [r['score'] for r in results]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(series, marker='o', linestyle='-', color='#9147ff', alpha=0.8, label=label)
    ax1.axhline(y=sum(series) / len(series), color='gray', linestyle='--', label='Average')
    ax1.set_title(f"{name} — {label}")
    ax1.set_ylabel(unit or label)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(scores, color='#00b5ad', linewidth=2, label=f'Predictability ({window_size}-match window)')
    ax2.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
    ax2.axhline(y=60, color='orange', linestyle='--', label='Volatile')
    ax2.set_title("Stability Analysis")
    ax2.set_ylabel("Score (0-100)")
    ax2.set_xlabel("Match #")
    ax2.set_ylim(0, 105)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    out_dir = os.path.join("static", "images", "esports_charts")
    os.makedirs(out_dir, exist_ok=True)
    fname = filename or f"{name.replace(' ', '_')}_{label}.png"
    path = os.path.join(out_dir, fname)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Chart saved → {path}")


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Esports Predictability Generator")
    print("=================================")
    print("Modes:")
    print("  1. Twitch Viewer Counts (live API or synthetic)")
    print("  2. K/D Ratio Series (synthetic)")
    print("  3. Win Rate Series (synthetic)")
    print("  4. Tournament Placements (synthetic)")
    print()

    while True:
        mode = input("Select mode (1-4) or 'q' to quit: ").strip()
        if mode.lower() == 'q':
            break

        if mode == '1':
            term = input("Search term (e.g. 'Valorant', 'CS2', 'Capcom Cup'): ").strip() or "Valorant"
            series = twitch_search_viewers(term)
            _print_series(f"Twitch: {term}", series, " viewers")
            _save_chart(term, series, "Viewers", "Viewer Count")

        elif mode == '2':
            name = input("Player name (label): ").strip() or "Player"
            n = int(input("Number of matches (default 20): ").strip() or "20")
            base_kd = float(input("Base K/D ratio (default 1.2): ").strip() or "1.2")
            series = kd_ratio_series(n=n, base_kd=base_kd)
            _print_series(f"{name} K/D", series)
            _save_chart(name, series, "KD_Ratio")

        elif mode == '3':
            name = input("Team/player name: ").strip() or "Team"
            n = int(input("Number of windows (default 30): ").strip() or "30")
            base_rate = float(input("Base win rate 0-1 (default 0.55): ").strip() or "0.55")
            series = win_rate_series(n=n, base_rate=base_rate)
            _print_series(f"{name} Win Rate", series)
            _save_chart(name, series, "Win_Rate")

        elif mode == '4':
            name = input("Player/org name: ").strip() or "Org"
            n = int(input("Number of tournaments (default 12): ").strip() or "12")
            avg_p = float(input("Average placement (default 4): ").strip() or "4")
            series = tournament_placements(n=n, avg_place=avg_p)
            _print_series(f"{name} Placements", series, " place")
            _save_chart(name, series, "Tournament_Place")

        else:
            print("Invalid choice.")