"""
synthetic_gen.py — Synthetic Time-Series Generator
====================================================
Generate realistic synthetic data series for testing the FSR engine
across a variety of real-world patterns.

Patterns available:
  • Random walk       — Brownian motion / unpredictable drift
  • Monte Carlo paths — GBM simulation, returns mean path
  • ARIMA forecast    — from a provided seed series (requires statsmodels)
  • Seasonal         — sinusoidal cycle + noise
  • Trending         — linear upward/downward trend + noise
  • Cyclical burst   — periodic spikes (like viral campaigns)
  • Mean-reverting   — Ornstein-Uhlenbeck process
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

K_SYNTHETIC = 1.0  # Neutral k-factor for generic synthetic data

try:
    from statsmodels.tsa.arima.model import ARIMA
    STATS_MODELS = True
except ImportError:
    STATS_MODELS = False


# ---------------------------------------------------------------------------
# Core generators
# ---------------------------------------------------------------------------

def random_walk(n=100, mu=0.0, sigma=1.0, seed=None):
    """Cumulative random walk (Brownian motion)."""
    rng = np.random.default_rng(seed)
    series = np.cumsum(rng.normal(mu, sigma, size=n)).round(4).tolist()
    return _run("random_walk", series)


def monte_carlo_paths(base=100.0, n_steps=60, n_paths=1000, mu=0.0, sigma=0.02, seed=None):
    """Geometric Brownian Motion — returns the mean path across n_paths simulations."""
    rng = np.random.default_rng(seed)
    paths = base * np.exp(np.cumsum(rng.normal(mu, sigma, size=(n_steps, n_paths)), axis=0))
    mean_path = paths.mean(axis=1).round(4).tolist()
    return _run("monte_carlo_mean", mean_path)


def arima_forecast(series, order=(1, 0, 0), steps=30):
    """
    Fit an ARIMA model to a seed series and forecast `steps` ahead.
    Requires statsmodels: pip install statsmodels
    """
    if not STATS_MODELS:
        print("statsmodels not installed. Run: pip install statsmodels")
        return None
    model = ARIMA(series, order=order)
    res = model.fit()
    fc = res.forecast(steps=steps).round(4).tolist()
    return _run("arima_forecast", fc)


def seasonal_series(n=52, amplitude=20, period=12, noise_sigma=5.0, base=100.0, seed=None):
    """
    Sinusoidal seasonal pattern (e.g., weekly retail sales, quarterly revenue).
    n=52 → 1 year of weekly data. period=12 → 12-week seasonal cycle.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    signal = base + amplitude * np.sin(2 * np.pi * t / period)
    noise = rng.normal(0, noise_sigma, size=n)
    series = (signal + noise).round(2).tolist()
    return _run("seasonal", series)


def trending_series(n=60, start=50.0, slope=1.5, noise_sigma=5.0, seed=None):
    """
    Linear trend with Gaussian noise (e.g., growing revenue, declining churn).
    slope > 0 → uptrend; slope < 0 → downtrend.
    """
    rng = np.random.default_rng(seed)
    trend = start + slope * np.arange(n)
    noise = rng.normal(0, noise_sigma, size=n)
    series = (trend + noise).round(2).tolist()
    return _run("trending", series)


def cyclical_burst(n=30, base=1000, burst_every=7, burst_multiplier=5.0, noise_sigma=100, seed=None):
    """
    Periodic spike pattern — like weekly viral content or scheduled promotions.
    burst_every → period between spikes (in data points).
    """
    rng = np.random.default_rng(seed)
    series = []
    for i in range(n):
        val = base + rng.normal(0, noise_sigma)
        if i % burst_every == 0:
            val *= burst_multiplier
        series.append(max(0, round(float(val), 2)))
    return _run("cyclical_burst", series)


def mean_reverting(n=60, mu=100.0, theta=0.3, sigma=10.0, start=100.0, seed=None):
    """
    Ornstein-Uhlenbeck mean-reverting process.
    Great for modeling prices, rates, or any quantity that drifts but returns to a mean.
    theta → speed of mean reversion (0-1); sigma → volatility.
    """
    rng = np.random.default_rng(seed)
    series = [start]
    for _ in range(n - 1):
        prev = series[-1]
        drift = theta * (mu - prev)
        shock = sigma * rng.normal()
        series.append(round(prev + drift + shock, 4))
    return _run("mean_reverting", series)


# ---------------------------------------------------------------------------
# Shared display + chart
# ---------------------------------------------------------------------------

def _run(name, series, k=K_SYNTHETIC):
    if not series or len(series) < 2:
        print("Not enough data.")
        return series

    score = calculate_predictability(series, k=k)
    avg = sum(series) / len(series)

    output = ", ".join(map(str, series))
    print(f"\n{name} ({len(series)} points)")
    print(f"\n--- COPY DATA ---\n{output}\n")
    print(f"Predictability Score : {score:.2f}")
    print(f"Average              : {avg:.4f}")

    _save_chart(name, series, k)
    return series


def _save_chart(name, series, k=K_SYNTHETIC):
    window_size = min(10, len(series) // 2)
    if window_size < 2:
        return
    results = calculate_sliding_window(series, window_size, k=k)
    scores = [None] * (window_size - 1) + [r['score'] for r in results]
    avg = sum(series) / len(series)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(series, linestyle='-', color='#0288d1', alpha=0.8, label=name)
    ax1.axhline(y=avg, color='gray', linestyle='--', label=f'Avg ({avg:.2f})')
    ax1.set_title(f"Synthetic: {name}")
    ax1.set_ylabel("Value")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(scores, color='#f57c00', linewidth=2, label=f'Predictability ({window_size}-pt window)')
    ax2.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
    ax2.axhline(y=60, color='orange', linestyle='--', label='Volatile')
    ax2.set_title("Stability Analysis")
    ax2.set_ylabel("Score (0-100)")
    ax2.set_xlabel("Step")
    ax2.set_ylim(0, 105)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    out_dir = os.path.join("static", "images", "synthetic_charts")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}_analysis.png")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Chart saved → {path}")


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

MENU = {
    "1": ("Random Walk",        "Brownian motion — completely unpredictable drift"),
    "2": ("Monte Carlo",        "GBM simulation — returns mean of N paths"),
    "3": ("ARIMA Forecast",     "Fit ARIMA to a seed series and forecast ahead"),
    "4": ("Seasonal",           "Sinusoidal pattern + noise (weekly, quarterly cycles)"),
    "5": ("Trending",           "Linear uptrend or downtrend + noise"),
    "6": ("Cyclical Burst",     "Periodic spikes — viral campaigns, scheduled events"),
    "7": ("Mean-Reverting",     "Ornstein-Uhlenbeck — drifts but returns to mean"),
}

if __name__ == "__main__":
    print("Synthetic Time-Series Generator")
    print("================================")
    for k, (name, desc) in MENU.items():
        print(f"  {k}. {name:<20} — {desc}")
    print()

    while True:
        mode = input("Select mode (1-7) or 'q' to quit: ").strip()
        if mode.lower() == 'q':
            break

        if mode == '1':
            n = int(input("Steps (default 100): ").strip() or "100")
            mu = float(input("Drift mu (default 0.0): ").strip() or "0.0")
            sigma = float(input("Volatility sigma (default 1.0): ").strip() or "1.0")
            random_walk(n=n, mu=mu, sigma=sigma)

        elif mode == '2':
            n = int(input("Steps (default 60): ").strip() or "60")
            paths = int(input("Simulated paths (default 1000): ").strip() or "1000")
            base = float(input("Starting value (default 100): ").strip() or "100")
            sigma = float(input("Daily volatility sigma (default 0.02): ").strip() or "0.02")
            monte_carlo_paths(base=base, n_steps=n, n_paths=paths, sigma=sigma)

        elif mode == '3':
            if not STATS_MODELS:
                print("statsmodels not installed. Run: pip install statsmodels")
                continue
            raw = input("Seed series (comma-separated numbers): ").strip()
            try:
                seed_series = [float(x) for x in raw.split(",") if x.strip()]
                steps = int(input("Forecast steps (default 30): ").strip() or "30")
                arima_forecast(seed_series, steps=steps)
            except ValueError:
                print("Invalid input.")

        elif mode == '4':
            n = int(input("Points (default 52): ").strip() or "52")
            period = int(input("Season period (default 12): ").strip() or "12")
            amp = float(input("Amplitude (default 20): ").strip() or "20")
            base = float(input("Base value (default 100): ").strip() or "100")
            seasonal_series(n=n, amplitude=amp, period=period, base=base)

        elif mode == '5':
            n = int(input("Points (default 60): ").strip() or "60")
            start = float(input("Starting value (default 50): ").strip() or "50")
            slope = float(input("Slope per step (default 1.5, negative for downtrend): ").strip() or "1.5")
            noise = float(input("Noise sigma (default 5): ").strip() or "5")
            trending_series(n=n, start=start, slope=slope, noise_sigma=noise)

        elif mode == '6':
            n = int(input("Points (default 30): ").strip() or "30")
            base = int(input("Base value (default 1000): ").strip() or "1000")
            every = int(input("Burst every N points (default 7): ").strip() or "7")
            mult = float(input("Burst multiplier (default 5x): ").strip() or "5")
            cyclical_burst(n=n, base=base, burst_every=every, burst_multiplier=mult)

        elif mode == '7':
            n = int(input("Points (default 60): ").strip() or "60")
            mu = float(input("Long-run mean (default 100): ").strip() or "100")
            theta = float(input("Reversion speed 0-1 (default 0.3): ").strip() or "0.3")
            sigma = float(input("Volatility sigma (default 10): ").strip() or "10")
            start = float(input("Starting value (default 100): ").strip() or "100")
            mean_reverting(n=n, mu=mu, theta=theta, sigma=sigma, start=start)

        else:
            print("Invalid choice.")