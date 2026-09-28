#!/usr/bin/env python3
"""
stock_fsr_chart.py — Single Stock FSR Chart (YouTube Edition)
=============================================================
Pulls multi-year daily price data via yfinance, runs FSR sliding window,
outputs a YouTube-ready 1920x1080 dark dual-axis chart.

Usage:
    python stock_fsr_chart.py ADBE
    python stock_fsr_chart.py NVDA
    python stock_fsr_chart.py TSLA
"""

import sys
import numpy as np
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── CONFIG ────────────────────────────────────────────────────────────────────
TICKER   = sys.argv[1].upper() if len(sys.argv) > 1 else "ADBE"
PERIOD   = "5y"
INTERVAL = "1d"
WINDOW   = 126    # ~6 months of trading days
K_FACTOR = 2.0

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG    = '#000000'
PANEL = '#050508'
GRID  = '#1a1a2e'
TEXT  = '#d4d4f0'
DIM   = '#5a5a8a'
WHITE = '#f0f0ff'
GREEN = '#00e676'
GOLD  = '#ffca28'
RED   = '#e53935'
BLUE  = '#29b6f6'

def score_color(s):
    if s >= 70: return GREEN
    if s >= 45: return GOLD
    return RED

def score_label(s):
    if s >= 70: return 'CONSISTENT'
    if s >= 45: return 'MODERATE'
    return 'VOLATILE'

# ── FETCH ─────────────────────────────────────────────────────────────────────
print(f'Fetching {TICKER} ({PERIOD}, {INTERVAL})...')
raw = yf.download(TICKER, period=PERIOD, interval=INTERVAL,
                  auto_adjust=True, progress=False)
if raw.empty:
    print(f'ERROR: No data for {TICKER}')
    sys.exit(1)

prices = raw['Close'].dropna()
dates  = prices.index.to_pydatetime()
vals   = prices.values.flatten().tolist()
print(f'  {len(vals)} trading days  |  latest: ${vals[-1]:.2f}  ({dates[-1].strftime("%Y-%m-%d")})')

# ── FSR ───────────────────────────────────────────────────────────────────────
current_score = calculate_predictability(vals[-WINDOW:], k=K_FACTOR)
sw_results    = calculate_sliding_window(vals, WINDOW, k=K_FACTOR)
sw_scores     = [r['score'] for r in sw_results]
sw_dates      = [dates[r['window_end'] - 1] for r in sw_results]

print(f'  FSR Score: {current_score:.1f}  [{score_label(current_score)}]')

# ── CHART ─────────────────────────────────────────────────────────────────────
fig, ax1 = plt.subplots(figsize=(19.2, 7.2), dpi=100)
fig.patch.set_facecolor(BG)
ax1.set_facecolor(PANEL)
for sp in ax1.spines.values():
    sp.set_edgecolor(GRID)

# Price area
ax1.fill_between(dates, vals, alpha=0.25, color=BLUE)
ax1.plot(dates, vals, color=BLUE, linewidth=1.8, label=f'{TICKER} Price')
ax1.set_ylabel('Stock Price ($)', color=BLUE, fontsize=12)
ax1.tick_params(axis='y', labelcolor=BLUE, labelsize=10)
ax1.tick_params(axis='x', labelcolor=TEXT, labelsize=10)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'${x:,.0f}'))
ax1.grid(True, color=GRID, linewidth=0.4, alpha=0.6)

# FSR line
ax2 = ax1.twinx()
ax2.plot(sw_dates, sw_scores, color=RED, linewidth=2.5,
         label=f'FSR Score ({WINDOW//21}-mo window)')
ax2.set_ylabel('Predictability Score (0-100)', color=RED, fontsize=12)
ax2.tick_params(axis='y', labelcolor=RED, labelsize=10)
ax2.set_ylim(0, 105)

# Threshold lines
ax2.axhline(70, color=GREEN, linewidth=0.7, linestyle='--', alpha=0.4)
ax2.axhline(45, color=GOLD,  linewidth=0.7, linestyle='--', alpha=0.4)

# Latest FSR dot
ax2.scatter([sw_dates[-1]], [sw_scores[-1]],
            color=score_color(current_score), s=80, zorder=10,
            edgecolors=BG, linewidths=1.5)

# Date axis
ax1.xaxis.set_major_locator(mdates.YearLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
plt.setp(ax1.get_xticklabels(), color=TEXT)

# Legend
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
legend = ax2.legend(lines1 + lines2, labels1 + labels2,
                    loc='upper right', facecolor='#0d0d1c',
                    edgecolor=GRID, labelcolor=TEXT, fontsize=11)
for t in legend.get_texts():
    t.set_fontfamily('monospace')

# Title
sc = score_color(current_score)
fig.text(0.5, 0.97,
         f'{TICKER} — Forecast Stability Rating (FSR)',
         ha='center', fontsize=20, fontweight='bold',
         color=WHITE, fontfamily='monospace')
fig.text(0.5, 0.925,
         f'Current Score: {current_score:.1f}/100  |  K={K_FACTOR} (Finance)  |  {score_label(current_score)}',
         ha='center', fontsize=13, color=sc, fontfamily='monospace')

fig.text(0.99, 0.01,
         f'predictability-api.com  ·  Data: Yahoo Finance  ·  {datetime.now().strftime("%Y-%m-%d")}',
         ha='right', fontsize=8, color='#2a2a45', fontfamily='monospace')

fig.tight_layout(rect=[0, 0.02, 1, 0.90])

out = f'{TICKER.lower()}_fsr.png'
plt.savefig(out, dpi=100, facecolor=BG, bbox_inches='tight')
plt.close()
print(f'Saved: {out}')
