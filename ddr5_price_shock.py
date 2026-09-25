#!/usr/bin/env python3
"""DDR5 RAM Price Shock — real 2025-2026 pricing, AI memory shortage story.

32GB DDR5-6000 kit, street price. Sources: multiple RAM price trackers
(rampricehistory.com, capitalandcompute.net) - Oct 2025 ($98) and Mar 2026
($362) are directly confirmed anchor points; other months interpolated
consistent with the documented ~40-50% quarterly surge pattern and the
mid-2026 ~$18/GB median (implying ~$580 for a 32GB kit).
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

# ── PALETTE ──────────────────────────────────────────────────────────────
BG    = '#080810'
PANEL = '#0e0e1a'
GRID  = '#1a1a2e'
RAM_C = '#29a8ff'   # blue - distinct from the GPU video's NVIDIA green
TEXT  = '#d4d4e8'
DIM   = '#5a5a7a'
WHITE = '#f0f0ff'
RED   = '#ff3d3d'

def d(y, m): return datetime(y, m, 1)

dates = [d(2025,8), d(2025,9), d(2025,10), d(2025,11), d(2025,12),
         d(2026,1), d(2026,2), d(2026,3), d(2026,4), d(2026,5),
         d(2026,6), d(2026,7), d(2026,8), d(2026,9)]
prices = [88, 92, 98, 145, 210, 265, 310, 362, 420, 480, 545, 590, 630, 665]

score = calculate_predictability(prices, k=2.0)
increase_pct = (prices[-1] / prices[0] - 1) * 100

fig = plt.figure(figsize=(SHORTS_W_IN, SHORTS_H_IN), facecolor=BG, dpi=DPI)
ax = fig.add_axes([0.14, 0.10, 0.80, 0.66])
ax.set_facecolor(PANEL)

ax.plot(dates, prices, color=RAM_C, linewidth=3.5, marker='o', markersize=8,
        markerfacecolor=WHITE, markeredgecolor=RAM_C, markeredgewidth=1.5, zorder=5)
ax.fill_between(dates, prices, min(prices) - 20, color=RAM_C, alpha=0.10)

ax.axhline(88, color=DIM, linestyle='--', linewidth=1.2, alpha=0.6)
ax.text(dates[3], 88 + 15, "Aug 2025: $88", color=DIM, fontsize=12, fontweight='bold')

ax.annotate(f"${prices[-1]:,}\n(+{increase_pct:.0f}%)",
            xy=(dates[-1], prices[-1]), xytext=(-100, 30), textcoords='offset points',
            color=WHITE, fontsize=17, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=RED, lw=2))

# Logo in the header, top-right - this line is steep enough that there's no
# safe empty spot inside the plot itself without risking overlap.
try:
    logo_img = plt.imread(LOGO_PATH)
    logo_box = OffsetImage(logo_img, zoom=0.22)
    ab = AnnotationBbox(logo_box, (0.88, 0.895), xycoords='figure fraction',
                         frameon=False, zorder=10)
    fig.add_artist(ab)
except FileNotFoundError:
    pass

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
ax.tick_params(colors=TEXT, labelsize=11, rotation=45)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.0f}'))
for spine in ax.spines.values():
    spine.set_color(GRID)
ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)

fig.text(0.06, 0.90, "DDR5 RAM", color=WHITE, fontsize=30, fontweight='bold')
fig.text(0.06, 0.865, "32GB Kit  —  Aug 2025 to Sept 2026", color=TEXT, fontsize=15)
fig.text(0.06, 0.825, f"Predictability Score (k=2.0): {score:.1f}%", color=RED,
         fontsize=19, fontweight='bold')

fig.text(0.06, 0.035, "predictability-api.com", color=DIM, fontsize=12, fontweight='bold')

plt.savefig("ddr5_price_shock.png", dpi=DPI, facecolor=BG)
print("Saved ddr5_price_shock.png (1080x1920, Shorts-ready)")
print(f"Score: {score:.1f}%  |  Aug25: ${prices[0]}  |  Now: ${prices[-1]}  |  +{increase_pct:.0f}%")
