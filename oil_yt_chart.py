#!/usr/bin/env python3
"""
oil_yt_chart.py — Oil Market FSR Comparison (YouTube Edition)
=============================================================
Pulls 1 year of daily data for oil futures + energy stocks,
runs FSR, outputs a YouTube-ready 1920x1080 dark chart.

Usage:  python oil_yt_chart.py
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
import yfinance as yf
from datetime import datetime, timedelta

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── TICKERS ───────────────────────────────────────────────────────────────────
# Group 1: Oil benchmarks (left panel)
OIL = [
    {"sym": "USO",  "name": "US Oil ETF",      "color": "#29b6f6"},
    {"sym": "CL=F", "name": "WTI Crude",       "color": "#ef5350"},
    {"sym": "BZ=F", "name": "Brent Crude",     "color": "#ffd54f"},
]
# Group 2: Energy equities (right panel)
ENERGY = [
    {"sym": "XLE",  "name": "Energy ETF",      "color": "#66bb6a"},
    {"sym": "XOM",  "name": "ExxonMobil",      "color": "#ab47bc"},
    {"sym": "CVX",  "name": "Chevron",         "color": "#ff7043"},
]

PERIOD   = "1y"
INTERVAL = "1d"
K_FACTOR = 2.0
WINDOW   = 20
OUT_FILE = "oil_yt_chart.png"

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG    = '#080810'
PANEL = '#0d0d1c'
GRID  = '#1a1a2e'
TEXT  = '#d4d4f0'
DIM   = '#5a5a8a'
WHITE = '#f0f0ff'
GREEN = '#00e676'
GOLD  = '#ffca28'
RED   = '#ff3d3d'

# ── FETCH ─────────────────────────────────────────────────────────────────────
def fetch(tickers):
    syms = [t["sym"] for t in tickers]
    print(f"  Fetching: {', '.join(syms)}")
    raw  = yf.download(syms, period=PERIOD, interval=INTERVAL,
                       progress=False, auto_adjust=True)
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw

    results = []
    for t in tickers:
        sym = t["sym"]
        if sym not in closes.columns:
            print(f"  [{sym}] not found")
            continue
        series = closes[sym].dropna().tolist()
        if len(series) < WINDOW + 2:
            print(f"  [{sym}] insufficient data ({len(series)} pts)")
            continue
        score = calculate_predictability(series, k=K_FACTOR)
        # Normalize to 100 at start for relative comparison
        base  = series[0]
        norm  = [round(v / base * 100, 4) for v in series]
        results.append({**t, "raw": series, "norm": norm, "score": score})
        print(f"  [{sym}] {len(series)} days | FSR: {score:.1f}")
    return results

# ── HELPERS ───────────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 70: return GREEN
    if s >= 50: return GOLD
    return RED

def score_label(s):
    if s >= 80: return 'STABLE'
    if s >= 65: return 'MODERATE'
    if s >= 50: return 'VOLATILE'
    return 'CHAOTIC'

def style_ax(ax):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.grid(color=GRID, linewidth=0.5, alpha=0.8)

def glow_plot(ax, xs, ys, color, lw=2.2, label='', zorder=5):
    ax.plot(xs, ys, color=color, alpha=0.08, linewidth=lw*5,   zorder=zorder-1, solid_capstyle='round')
    ax.plot(xs, ys, color=color, alpha=0.22, linewidth=lw*2.5, zorder=zorder,   solid_capstyle='round')
    ax.plot(xs, ys, color=color, linewidth=lw,                 zorder=zorder+1, label=label, solid_capstyle='round')
    ax.scatter([xs[-1]], [ys[-1]], color=color, s=45, zorder=zorder+2,
               edgecolors=BG, linewidths=1.2)

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart(oil_data, energy_data):
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(
        3, 3,
        width_ratios=[1.15, 1.15, 0.65],
        height_ratios=[1.5, 1.5, 1],
        hspace=0.38, wspace=0.28,
        left=0.05, right=0.97,
        top=0.87, bottom=0.07,
    )

    ax_oil_raw    = fig.add_subplot(gs[0, 0])   # oil raw prices
    ax_energy_raw = fig.add_subplot(gs[0, 1])   # energy stock raw prices
    ax_oil_rel    = fig.add_subplot(gs[1, 0])   # oil normalized (relative)
    ax_energy_rel = fig.add_subplot(gs[1, 1])   # energy normalized (relative)
    ax_fsr        = fig.add_subplot(gs[2, :2])  # FSR rolling window (both groups)
    ax_badge      = fig.add_subplot(gs[:, 2])   # score badges

    for ax in [ax_oil_raw, ax_energy_raw, ax_oil_rel, ax_energy_rel, ax_fsr, ax_badge]:
        style_ax(ax)

    n = max(len(d['raw']) for d in oil_data + energy_data) if oil_data + energy_data else 200
    xs = list(range(1, n + 1))

    # ── RAW PRICE PANELS ──────────────────────────────────────────────────────
    for ax, data, title in [
        (ax_oil_raw,    oil_data,    'Oil Futures — Raw Price (USD)'),
        (ax_energy_raw, energy_data, 'Energy Stocks — Raw Price (USD)'),
    ]:
        for r in data:
            ys = r['raw']
            x  = list(range(1, len(ys) + 1))
            glow_plot(ax, x, ys, r['color'], lw=2.0,
                      label=f"{r['sym']}  {r['score']:.1f}")
        ax.set_title(title, color=WHITE, fontsize=11, fontfamily='monospace', pad=8)
        ax.set_ylabel('Price (USD)', color=TEXT, fontsize=9)
        ax.set_xlim(0, n + 1)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'${v:,.0f}'))
        leg = ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                        fontsize=9, loc='upper left', handlelength=2)
        for t in leg.get_texts():
            t.set_fontfamily('monospace')

    # ── RELATIVE (NORMALIZED) PANELS ──────────────────────────────────────────
    for ax, data, title in [
        (ax_oil_rel,    oil_data,    'Oil — Relative Performance (base = 100)'),
        (ax_energy_rel, energy_data, 'Energy Stocks — Relative Performance'),
    ]:
        ax.axhline(100, color=DIM, linewidth=0.8, linestyle='--', alpha=0.5)
        for r in data:
            ys = r['norm']
            x  = list(range(1, len(ys) + 1))
            glow_plot(ax, x, ys, r['color'], lw=2.0, label=r['sym'])
            # end label
            ax.text(len(ys) + 0.5, ys[-1], f"{ys[-1]:.1f}",
                    color=r['color'], fontsize=8, va='center', fontfamily='monospace')
        ax.set_title(title, color=WHITE, fontsize=11, fontfamily='monospace', pad=8)
        ax.set_ylabel('Relative (start=100)', color=TEXT, fontsize=9)
        ax.set_xlim(0, n + 8)
        leg = ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                        fontsize=9, loc='upper left', handlelength=2)
        for t in leg.get_texts():
            t.set_fontfamily('monospace')

    # ── FSR ROLLING WINDOW ────────────────────────────────────────────────────
    all_data = oil_data + energy_data
    for r in all_data:
        if len(r['raw']) < WINDOW + 1:
            continue
        sw   = calculate_sliding_window(r['raw'], WINDOW, k=K_FACTOR)
        sw_y = [res['score'] for res in sw]
        sw_x = list(range(WINDOW, len(r['raw']) + 1))
        ax_fsr.plot(sw_x, sw_y, color=r['color'], alpha=0.10, linewidth=6,   zorder=2)
        ax_fsr.plot(sw_x, sw_y, color=r['color'], alpha=0.28, linewidth=3,   zorder=3)
        ax_fsr.plot(sw_x, sw_y, color=r['color'], linewidth=1.6,             zorder=4,
                    label=f"{r['sym']}  {r['score']:.1f}")
        ax_fsr.scatter([sw_x[-1]], [sw_y[-1]], color=r['color'], s=40,
                       zorder=5, edgecolors=BG, linewidths=1.2)

    ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.45)
    ax_fsr.axhline(50, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.45)
    ax_fsr.text(1, 71.5, 'STABLE',   color=GREEN, fontsize=7.5, alpha=0.55, fontfamily='monospace')
    ax_fsr.text(1, 51.5, 'VOLATILE', color=GOLD,  fontsize=7.5, alpha=0.55, fontfamily='monospace')
    ax_fsr.set_xlim(0, n + 1)
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_xlabel(f'Trading Day (1 year)  ·  {WINDOW}-day rolling FSR window', color=DIM, fontsize=9)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10)
    ax_fsr.set_title('FSR Predictability Score — Oil Futures vs Energy Stocks',
                     color=WHITE, fontsize=11, fontfamily='monospace', pad=8)
    leg = ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                        fontsize=9.5, loc='lower right', ncol=6,
                        handlelength=2, handletextpad=0.5)
    for t in leg.get_texts():
        t.set_fontfamily('monospace')

    # ── SCORE BADGES ──────────────────────────────────────────────────────────
    ax_badge.set_xlim(0, 1)
    ax_badge.set_ylim(0, 1)
    ax_badge.set_xticks([])
    ax_badge.set_yticks([])

    ax_badge.text(0.5, 0.978, 'FSR SCORES', ha='center', va='top',
                  fontsize=9.5, color=DIM, fontfamily='monospace', fontweight='bold')

    all_scored = sorted(all_data, key=lambda r: r['score'], reverse=True)
    slot = 0.90 / max(len(all_scored), 1)

    for i, r in enumerate(all_scored):
        cy = 0.93 - i * slot - slot * 0.25
        sc = score_color(r['score'])
        ax_badge.add_patch(plt.Circle((0.5, cy), 0.13, fill=False,
                                       edgecolor=sc, linewidth=2.5, alpha=0.9))
        ax_badge.text(0.5, cy + 0.015, f"{r['score']:.1f}",
                      ha='center', va='center', fontsize=16, fontweight='bold',
                      color=sc, fontfamily='monospace')
        ax_badge.text(0.5, cy - 0.065, r['sym'],
                      ha='center', fontsize=9, fontweight='bold',
                      color=r['color'], fontfamily='monospace')
        ax_badge.text(0.5, cy - 0.105, score_label(r['score']),
                      ha='center', fontsize=7, color=sc, fontfamily='monospace')

    # ── TITLES ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             'OIL MARKET PREDICTABILITY  —  FUTURES vs ENERGY STOCKS  (1 YEAR)',
             ha='center', fontsize=19, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.930,
             'USO  ·  WTI Crude  ·  Brent Crude  vs  XLE  ·  ExxonMobil  ·  Chevron  '
             '·  FSR Predictability Score™  ·  k=2.0 Finance',
             ha='center', fontsize=10, color=DIM, fontfamily='monospace')

    ts = datetime.now().strftime('%Y-%m-%d  %H:%M')
    fig.text(0.97, 0.012,
             f'Data: Yahoo Finance  ·  {ts}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    plt.savefig(OUT_FILE, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f"\nSaved: {OUT_FILE}")
    plt.show()

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Oil Market FSR Chart — YouTube Edition")
    print("=" * 42)
    print("\nFetching oil futures...")
    oil_data = fetch(OIL)
    print("\nFetching energy stocks...")
    energy_data = fetch(ENERGY)

    all_data = oil_data + energy_data
    print(f"\nScores:")
    for r in sorted(all_data, key=lambda x: x['score'], reverse=True):
        print(f"  {r['sym']:<6} {r['score']:.1f}  [{score_label(r['score'])}]")

    print("\nBuilding chart...")
    build_chart(oil_data, energy_data)
