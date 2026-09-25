#!/usr/bin/env python3
"""RTX 5090 Price Shock — real 2025-2026 pricing, AI memory shortage story.

Sources: Nvidia MSRP (launch), GPU Poet monthly averages (Jan/Mar/May/Jun 2026),
Tom's Hardware median tracker (Aug 2026), bestvaluegpu.com (Sept 2026).
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from datetime import datetime

from fsr import calculate_predictability

# YouTube Shorts frame: 1080x1920 (9:16). dpi=120 x figsize(9,16) = exact match.
SHORTS_W_IN, SHORTS_H_IN = 9, 16
DPI = 120
LOGO_PATH = "stream_infra/brand_logo.png"

# ── PALETTE (matches gpu_price_trends.py) ──────────────────────────────────
BG    = '#080810'
PANEL = '#0e0e1a'
GRID  = '#1a1a2e'
NV_C  = '#76b900'   # NVIDIA green
TEXT  = '#d4d4e8'
DIM   = '#5a5a7a'
WHITE = '#f0f0ff'
RED   = '#ff3d3d'

def d(y, m): return datetime(y, m, 1)

dates = [d(2025,1), d(2025,3), d(2025,5), d(2025,7), d(2025,9), d(2025,11),
         d(2026,1), d(2026,3), d(2026,5), d(2026,6), d(2026,7), d(2026,8), d(2026,9)]
prices = [1999, 1950, 1899, 1875, 1950, 2300, 3016, 3568, 3658, 3853, 4200, 4599, 4899]

score = calculate_predictability(prices, k=2.0)
increase_pct = (prices[-1] / prices[0] - 1) * 100

fig = plt.figure(figsize=(SHORTS_W_IN, SHORTS_H_IN), facecolor=BG, dpi=DPI)
# Generous fixed margins so nothing touches the frame edge on a phone screen.
ax = fig.add_axes([0.14, 0.10, 0.80, 0.66])
ax.set_facecolor(PANEL)

ax.plot(dates, prices, color=NV_C, linewidth=3.5, marker='o', markersize=8,
        markerfacecolor=WHITE, markeredgecolor=NV_C, markeredgewidth=1.5, zorder=5)
ax.fill_between(dates, prices, min(prices) - 200, color=NV_C, alpha=0.08)

ax.axhline(1999, color=DIM, linestyle='--', linewidth=1.2, alpha=0.6)
ax.text(dates[0], 1999 + 80, "Launch MSRP: $1,999", color=DIM, fontsize=12, fontweight='bold')

ax.annotate(f"${prices[-1]:,}\n(+{increase_pct:.0f}%)",
            xy=(dates[-1], prices[-1]), xytext=(-100, 30), textcoords='offset points',
            color=WHITE, fontsize=17, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=RED, lw=2))

# --- Logo in the empty upper-left region (line stays flat/low there until Nov25) ---
try:
    logo_img = plt.imread(LOGO_PATH)
    logo_box = OffsetImage(logo_img, zoom=0.28)
    ab = AnnotationBbox(logo_box, (dates[2], 4550), frameon=False, zorder=10)
    ax.add_artist(ab)
except FileNotFoundError:
    pass

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
ax.tick_params(colors=TEXT, labelsize=11, rotation=45)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.0f}'))
for spine in ax.spines.values():
    spine.set_color(GRID)
ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)

# --- Header text block, above the axes, own space so it can't collide with the plot ---
fig.text(0.06, 0.90, "RTX 5090", color=WHITE, fontsize=30, fontweight='bold')
fig.text(0.06, 0.865, "Price Shock  —  Jan 2025 to Sept 2026", color=TEXT, fontsize=15)
fig.text(0.06, 0.825, f"Predictability Score (k=2.0): {score:.1f}%", color=RED,
         fontsize=19, fontweight='bold')

fig.text(0.06, 0.035, "predictability-api.com", color=DIM, fontsize=12, fontweight='bold')

plt.savefig("rtx5090_price_shock.png", dpi=DPI, facecolor=BG)
print("Saved rtx5090_price_shock.png (1080x1920, Shorts-ready)")
print(f"Score: {score:.1f}%  |  Launch: ${prices[0]:,}  |  Now: ${prices[-1]:,}  |  +{increase_pct:.0f}%")
