"""
marketing_gen.py — Unified Marketing & Market Data Generator
=============================================================
Two modes:
  A. Campaign metrics  — reads CSV files with impression/click/revenue columns
  B. Financial market  — fetches live price data via yfinance (formerly marketing_data_gen.py)

Both compute the FSR Predictability Score™ and save charts.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

K_MARKETING = 2.0  # Finance standard — matches calculator Finance mode

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Mode A: Campaign / marketing CSV metrics
# ---------------------------------------------------------------------------

COMMON_METRICS = ["impressions", "clicks", "ctr", "revenue", "conversions", "spend", "roas"]


def analyze_campaign_csv(path, metric_column="impressions", date_column="date", tail=30):
    """
    Load a marketing CSV and run FSR analysis on any numeric metric column.
    Returns the predictability score.
    """
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        print(f"File not found: {path}")
        return None

    # Flexible date parsing
    if date_column in df.columns:
        try:
            df[date_column] = pd.to_datetime(df[date_column])
            df = df.sort_values(date_column)
        except Exception:
            pass

    # Find metric column (case-insensitive fuzzy)
    col_match = next(
        (c for c in df.columns if metric_column.lower() in c.lower()), None
    )
    if col_match is None:
        print(f"Column '{metric_column}' not found. Available: {', '.join(df.columns)}")
        return None

    series = df[col_match].dropna().tail(tail).astype(float).tolist()
    if len(series) < 2:
        print("Not enough data points.")
        return None

    label = f"{os.path.basename(path)} — {col_match}"
    return _run_analysis(label, series, unit=col_match)


# ---------------------------------------------------------------------------
# Mode B: Financial market data via yfinance
# ---------------------------------------------------------------------------

def get_market_data(ticker, period="2d", interval="1h"):
    """
    Fetch historical price data for any ticker via yfinance and run FSR analysis.
    Default: last 24 hours of hourly close prices.
    Returns predictability score.
    """
    if not YFINANCE_AVAILABLE:
        print("yfinance not installed. Run: pip install yfinance")
        return None

    print(f"\n--- Fetching {ticker} (period={period}, interval={interval}) ---")
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            print("No data returned — check the ticker symbol.")
            return None

        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"][ticker]
        else:
            close = data["Close"]

        close = close.dropna()

        # For default 24h view, keep last 24 points
        if period == "2d" and interval == "1h":
            close = close.tail(24)

        series = [round(float(x), 2) for x in close.tolist()]
        if len(series) < 2:
            print("Insufficient data points for analysis.")
            return None

        return _run_analysis(ticker, series, unit="Price")

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


# ---------------------------------------------------------------------------
# Shared analysis + display + chart
# ---------------------------------------------------------------------------

def _run_analysis(label, series, unit=""):
    score = calculate_predictability(series, k=K_MARKETING)
    avg = sum(series) / len(series)

    output = ", ".join(map(str, series))
    print(f"\n{label} ({len(series)} points)")
    print(f"\n--- COPY DATA ---\n{output}\n")
    print(f"Predictability Score : {score:.2f}")
    print(f"Average              : {avg:.2f}" + (f" ({unit})" if unit else ""))
    print(f"Suggested Target     : {round(avg, 2)}")

    _save_chart(label, series, unit)
    return score


def _save_chart(label, series, unit=""):
    window_size = min(10, len(series) // 2)
    if window_size < 2:
        return
    results = calculate_sliding_window(series, window_size, k=K_MARKETING)
    scores = [None] * (window_size - 1) + [r['score'] for r in results]
    avg = sum(series) / len(series)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(series, marker='o', linestyle='-', color='#e67e22', alpha=0.8, label=unit or label)
    ax1.axhline(y=avg, color='gray', linestyle='--', label=f'Avg ({avg:.2f})')
    ax1.set_title(f"{label}")
    ax1.set_ylabel(unit or "Value")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(scores, color='#2980b9', linewidth=2, label=f'Predictability ({window_size}-pt window)')
    ax2.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
    ax2.axhline(y=60, color='orange', linestyle='--', label='Volatile')
    ax2.set_title("Stability Analysis")
    ax2.set_ylabel("Score (0-100)")
    ax2.set_xlabel("Period")
    ax2.set_ylim(0, 105)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    out_dir = os.path.join("static", "images", "marketing_charts")
    os.makedirs(out_dir, exist_ok=True)
    safe = label.replace(" ", "_").replace("/", "_").replace("—", "").strip("_")[:40]
    path = os.path.join(out_dir, f"{safe}_analysis.png")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    print(f"Chart saved → {path}")


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Marketing & Market Data Generator")
    print("===================================")
    print("Modes:")
    print("  1. Campaign CSV  — analyze impressions, clicks, revenue, etc.")
    print("  2. Market prices — fetch live ticker data (yfinance)")
    print()

    while True:
        mode = input("Select mode (1-2) or 'q' to quit: ").strip()
        if mode.lower() == 'q':
            break

        if mode == '1':
            path = input("CSV file path (default: marketing_data.csv): ").strip() or "marketing_data.csv"
            print(f"Common metrics: {', '.join(COMMON_METRICS)}")
            metric = input("Metric column to analyze (default: impressions): ").strip() or "impressions"
            date_col = input("Date column name (default: date): ").strip() or "date"
            tail_n = int(input("Last N rows to analyze (default: 30): ").strip() or "30")
            analyze_campaign_csv(path, metric_column=metric, date_column=date_col, tail=tail_n)

        elif mode == '2':
            if not YFINANCE_AVAILABLE:
                print("yfinance not installed. Run: pip install yfinance")
                continue
            print("Examples: SPY, QQQ, BTC-USD, NVDA, AAPL")
            ticker = input("Ticker symbol: ").strip().upper()
            if not ticker:
                continue
            use_defaults = input("Use default (last 24h hourly)? (y/n, default y): ").strip().lower()
            if use_defaults == 'n':
                period = input("Period (e.g. 3mo, 5d, 1y): ").strip() or "3mo"
                interval = input("Interval (e.g. 1d, 1wk, 1mo): ").strip() or "1d"
            else:
                period, interval = "2d", "1h"
            get_market_data(ticker, period=period, interval=interval)

        else:
            print("Invalid choice.")