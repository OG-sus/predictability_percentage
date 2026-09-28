#!/usr/bin/env python3
"""
ai_prediction_audit.py — Wall Street AI Consensus Audit
=========================================================
Pulls 90 days of analyst consensus recommendations (Buy/Hold/Sell)
from Yahoo Finance, checks if the call matched actual price movement,
scores accuracy consistency with FSR, and outputs a YouTube-ready chart.

Usage:  python ai_prediction_audit.py
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import yfinance as yf
from datetime import datetime, timedelta

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── STOCKS ────────────────────────────────────────────────────────────────────
TICKERS = [
    {"sym": "MSTR",  "name": "MicroStrategy", "color": "#f7931a"},
    {"sym": "NVDA",  "name": "NVIDIA",         "color": "#76b900"},
    {"sym": "PLTR",  "name": "Palantir",       "color": "#1b75bc"},
    {"sym": "GME",   "name": "GameStop",       "color": "#e91e63"},
    {"sym": "TSLA",  "name": "Tesla",          "color": "#e82127"},
    {"sym": "AAPL",  "name": "Apple",          "color": "#555555"},
]

LOOKBACK_DAYS = 90
K_FACTOR      = 2.0   # Finance standard
WINDOW        = 6
OUT_FILE      = "ai_prediction_audit.png"

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG    = '#080810'
PANEL = '#0d0d1c'
GRID  = '#1a1a2e'
TEXT  = '#d4d4f0'
DIM   = '#5a5a8a'
WHITE = '#f0f0ff'
GREEN = '#00e676'
RED   = '#ff3d3d'
GOLD  = '#ffca28'

# ── DATA FETCH ────────────────────────────────────────────────────────────────
def recommendation_to_score(rec: str) -> float | None:
    """Map analyst rec string to directional score: +1 bullish, -1 bearish."""
    r = str(rec).lower().strip()
    if any(x in r for x in ['strong buy', 'strongbuy']):        return 1.0
    if any(x in r for x in ['buy', 'outperform', 'overweight']): return 0.7
    if any(x in r for x in ['hold', 'neutral', 'equal']):        return 0.0
    if any(x in r for x in ['underperform', 'underweight']):     return -0.7
    if any(x in r for x in ['sell', 'strong sell']):             return -1.0
    return None

def fetch_ticker_data(sym: str):
    """
    Pulls upgrades_downgrades from Yahoo Finance (individual dated analyst calls),
    checks each call against actual 5-day price movement, returns scored list.
    """
    t   = yf.Ticker(sym)
    end = datetime.today()

    # Price history
    hist = t.history(start=(end - timedelta(days=LOOKBACK_DAYS + 30)).strftime('%Y-%m-%d'),
                     end=end.strftime('%Y-%m-%d'), interval='1d')
    if hist.empty or len(hist) < 5:
        print(f"  [{sym}] No price data")
        return []
    hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index

    # Individual analyst calls
    try:
        recs = t.upgrades_downgrades
    except Exception as e:
        print(f"  [{sym}] Error fetching upgrades_downgrades: {e}")
        return []

    if recs is None or recs.empty:
        print(f"  [{sym}] No analyst data")
        return []

    recs.index = recs.index.tz_localize(None) if recs.index.tz else recs.index
    cutoff = end - timedelta(days=LOOKBACK_DAYS)
    recs   = recs[recs.index >= cutoff].sort_index()

    if recs.empty:
        print(f"  [{sym}] No calls in last {LOOKBACK_DAYS} days")
        return []

    closes  = hist['Close']
    results = []

    for date, row in recs.iterrows():
        grade     = str(row.get('ToGrade', row.get('To Grade', ''))).strip()
        direction = recommendation_to_score(grade)
        if direction is None:
            continue

        past_dates   = closes.index[closes.index <= date]
        future_dates = closes.index[closes.index > date]
        if len(past_dates) == 0 or len(future_dates) < 5:
            continue

        base_close   = closes.loc[past_dates[-1]]
        future_close = closes.loc[future_dates[4]]
        ret = (future_close - base_close) / base_close

        if direction > 0:
            correct = 1.0 if ret > 0.005 else 0.0
        elif direction < 0:
            correct = 1.0 if ret < -0.005 else 0.0
        else:
            correct = 1.0 if abs(ret) < 0.02 else 0.0

        results.append({
            'date':      date,
            'firm':      str(row.get('Firm', '')),
            'grade':     grade,
            'direction': direction,
            'ret_5d':    round(ret * 100, 2),
            'correct':   correct,
        })

    print(f"  [{sym}] {len(results)} scored calls")
    return results


# ── SCORE COLOR ───────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 70: return GREEN
    if s >= 50: return GOLD
    return RED

def score_label(s):
    if s >= 80: return 'RELIABLE'
    if s >= 65: return 'DECENT'
    if s >= 50: return 'COIN FLIP'
    if s >= 35: return 'UNRELIABLE'
    return 'WRONG'

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart(all_results):
    valid = [r for r in all_results if r['calls']]
    if not valid:
        print("No data to chart.")
        return

    n = len(valid)
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(
        2, n + 1,
        width_ratios=[1] * n + [0.7],
        height_ratios=[1.4, 1],
        hspace=0.42, wspace=0.28,
        left=0.04, right=0.97,
        top=0.87, bottom=0.09,
    )

    # ── TOP ROW: per-stock correct/wrong bars ──────────────────────────────────
    for col, r in enumerate(valid):
        ax = fig.add_subplot(gs[0, col])
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.tick_params(colors=TEXT, labelsize=8)

        calls   = r['calls']
        correct = [c['correct'] for c in calls]
        xs      = list(range(1, len(calls) + 1))
        colors  = [GREEN if c == 1.0 else RED for c in correct]
        acc     = sum(correct) / len(correct) * 100

        ax.bar(xs, [1] * len(xs), color=colors, width=0.8, alpha=0.85, zorder=3)
        ax.set_xlim(0, len(xs) + 1)
        ax.set_ylim(0, 1.4)
        ax.set_yticks([])
        ax.set_xticks([])

        ax.set_title(f"{r['sym']}  —  {r['name']}",
                     color=r['color'], fontsize=11, fontfamily='monospace',
                     fontweight='bold', pad=8)

        sc = score_color(r['score'])
        ax.text(len(xs) / 2 + 0.5, 1.12,
                f"{acc:.0f}% correct  ·  {len(calls)} calls",
                ha='center', fontsize=8.5, color=TEXT, fontfamily='monospace')

        ax.axhline(0.5, color=GRID, linewidth=0.5, alpha=0.5)
        ax.grid(axis='x', color=GRID, linewidth=0.4, alpha=0.4)

        correct_p = mpatches.Patch(color=GREEN, label='Correct')
        wrong_p   = mpatches.Patch(color=RED,   label='Wrong')
        ax.legend(handles=[correct_p, wrong_p], facecolor=PANEL,
                  edgecolor=GRID, labelcolor=TEXT, fontsize=7.5,
                  loc='lower right', handlelength=1)

    # ── BOTTOM: FSR rolling accuracy ────────────────────────────────────────────
    ax_fsr = fig.add_subplot(gs[1, :n])
    ax_fsr.set_facecolor(PANEL)
    for sp in ax_fsr.spines.values():
        sp.set_edgecolor(GRID)
    ax_fsr.tick_params(colors=TEXT, labelsize=9)

    max_calls = max(len(r['calls']) for r in valid)

    for r in valid:
        correct_series = [c['correct'] * 100 for c in r['calls']]
        if len(correct_series) < WINDOW + 1:
            ax_fsr.axhline(r['score'], color=r['color'], linewidth=1.5,
                           linestyle='--', alpha=0.6,
                           label=f"{r['sym']} ({r['score']:.1f})")
            continue

        sw   = calculate_sliding_window(correct_series, WINDOW, k=K_FACTOR)
        sw_y = [res['score'] for res in sw]
        sw_x = list(range(WINDOW, len(correct_series) + 1))

        ax_fsr.plot(sw_x, sw_y, color=r['color'], alpha=0.10, linewidth=7,   zorder=2)
        ax_fsr.plot(sw_x, sw_y, color=r['color'], alpha=0.28, linewidth=3.5, zorder=3)
        ax_fsr.plot(sw_x, sw_y, color=r['color'], linewidth=1.8,             zorder=4,
                    label=f"{r['sym']}  {r['score']:.1f}")
        ax_fsr.scatter([sw_x[-1]], [sw_y[-1]], color=r['color'], s=55,
                       zorder=5, edgecolors=BG, linewidths=1.5)

    ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.45)
    ax_fsr.axhline(50, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.45)
    ax_fsr.text(0.5, 71.5, 'RELIABLE', color=GREEN, fontsize=7.5,
                alpha=0.55, fontfamily='monospace')
    ax_fsr.text(0.5, 51.5, 'COIN FLIP', color=GOLD, fontsize=7.5,
                alpha=0.55, fontfamily='monospace')

    ax_fsr.set_xlim(0, max_calls + 1)
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_xlabel('Recommendation # (chronological)', color=DIM, fontsize=9)
    ax_fsr.set_ylabel('FSR Accuracy Score', color=TEXT, fontsize=10)
    ax_fsr.set_title(f'Prediction Consistency — {WINDOW}-Call Rolling Window',
                     color=WHITE, fontsize=12, fontfamily='monospace', pad=8)
    ax_fsr.grid(color=GRID, linewidth=0.5, alpha=0.7)
    ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                  fontsize=10, loc='lower right', ncol=n,
                  handlelength=2, handletextpad=0.5)

    # ── RIGHT: score badges ────────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[:, n])
    ax_b.set_facecolor(PANEL)
    for sp in ax_b.spines.values():
        sp.set_edgecolor(GRID)
    ax_b.set_xlim(0, 1)
    ax_b.set_ylim(0, 1)
    ax_b.set_xticks([])
    ax_b.set_yticks([])

    ax_b.text(0.5, 0.975, 'FSR ACCURACY', ha='center', va='top',
              fontsize=9, color=DIM, fontfamily='monospace', fontweight='bold')

    slot = 0.88 / max(len(valid), 1)
    for i, r in enumerate(valid):
        cy = 0.9 - i * slot - slot * 0.28
        sc = score_color(r['score'])
        ax_b.add_patch(plt.Circle((0.5, cy), 0.15, fill=False,
                                   edgecolor=sc, linewidth=3, alpha=0.9))
        ax_b.text(0.5, cy + 0.02, f"{r['score']:.1f}",
                  ha='center', va='center', fontsize=18, fontweight='bold',
                  color=sc, fontfamily='monospace')
        ax_b.text(0.5, cy - 0.08, r['sym'],
                  ha='center', fontsize=9.5, fontweight='bold',
                  color=r['color'], fontfamily='monospace')
        ax_b.text(0.5, cy - 0.132, score_label(r['score']),
                  ha='center', fontsize=7.5, color=sc, fontfamily='monospace')
        acc = sum(c['correct'] for c in r['calls']) / len(r['calls']) * 100
        ax_b.text(0.5, cy - 0.178, f"{acc:.0f}% hit rate",
                  ha='center', fontsize=7, color=DIM, fontfamily='monospace')

    # ── TITLES ─────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             'WALL STREET AI CONSENSUS  —  90-DAY PREDICTION AUDIT',
             ha='center', fontsize=20, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.930,
             f'Did analyst AI calls match reality?  ·  Green = correct  ·  Red = wrong  '
             f'·  FSR Predictability Score™  ·  Last {LOOKBACK_DAYS} days',
             ha='center', fontsize=10.5, color=DIM, fontfamily='monospace')

    ts = datetime.now().strftime('%Y-%m-%d  %H:%M')
    fig.text(0.97, 0.012,
             f'Data: Yahoo Finance  ·  {ts}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    plt.savefig(OUT_FILE, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f"\nSaved: {OUT_FILE}")
    plt.show()


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Wall Street AI Consensus Audit")
    print("=" * 42)
    print(f"Lookback: {LOOKBACK_DAYS} days  |  k={K_FACTOR}  |  window={WINDOW}\n")

    all_results = []
    for t in TICKERS:
        print(f"[{t['sym']}] {t['name']}")
        calls = fetch_ticker_data(t['sym'])
        if calls:
            correct_series = [c['correct'] * 100 for c in calls]
            score = calculate_predictability(correct_series, k=K_FACTOR)
            acc   = sum(c['correct'] for c in calls) / len(calls) * 100
            print(f"  FSR: {score:.1f}  |  Hit rate: {acc:.0f}%  |  [{score_label(score)}]")
        else:
            score = 0.0
        all_results.append({**t, "calls": calls, "score": score})
        print()

    print("Building chart...")
    build_chart(all_results)
