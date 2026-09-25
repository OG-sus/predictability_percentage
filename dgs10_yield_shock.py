#!/usr/bin/env python3
"""10-Year Treasury Yield — real FRED data (DGS10), May-Sept 2026.

Monthly anchor points (first trading day of month) plus the latest reading.
Source: FRED series DGS10, pulled live via fredapi.
  May 2026: 4.47%   Jun 2026: 4.47%   Jul 2026: 4.48%
  Aug 2026: 4.70%   Sep 2026: 4.79%   Sep 22, 2026 (latest): 4.96%
Flat for three months, then a real break upward - this is the yield that
drives mortgage rates, so it's the most "felt" of the treasury curve.
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from datetime import datetime

from fsr import calculate_predictability

SHORTS_W_IN, SHORTS_H_IN = 9, 16
DPI = 120
LOGO_PATH = "stream_infra/brand_logo.png"

BG    = '#080810'
PANEL = '#0e0e1a'
GRID  = '#1a1a2e'
Y_C   = '#ffb020'   # treasury/gold tone - distinct from the blue/green product shorts
TEXT  = '#d4d4e8'
DIM   = '#5a5a7a'
WHITE = '#f0f0ff'
RED   = '#ff3d3d'

def d(y, m, day=1): return datetime(y, m, day)

dates = [d(2026,5), d(2026,6), d(2026,7), d(2026,8), d(2026,9,1), d(2026,9,22)]
yields_ = [4.47, 4.47, 4.48, 4.70, 4.79, 4.96]

score = calculate_predictability(yields_, k=2.0)

# Same safe-zone margins as the PS5 short - keeps everything clear of the
# Shorts UI (like/comment/share column on the right, caption bar on the bottom).
SAFE_LEFT, SAFE_RIGHT = 0.075, 0.80
SAFE_TOP, SAFE_BOTTOM = 0.88, 0.205

fig = plt.figure(figsize=(SHORTS_W_IN, SHORTS_H_IN), facecolor=BG, dpi=DPI)
ax = fig.add_axes([SAFE_LEFT + 0.09, SAFE_BOTTOM + 0.02, SAFE_RIGHT - (SAFE_LEFT + 0.09) - 0.01, 0.44])
ax.set_facecolor(PANEL)

ax.plot(dates, yields_, color=Y_C, linewidth=3.5, marker='o', markersize=8,
        markerfacecolor=WHITE, markeredgecolor=Y_C, markeredgewidth=1.5, zorder=5)
ax.fill_between(dates, yields_, min(yields_) - 0.15, color=Y_C, alpha=0.10)
ax.set_xlim(dates[0], d(2026, 10, 5))

ax.axhline(4.47, color=DIM, linestyle='--', linewidth=1.2, alpha=0.6)
ax.text(dates[0], 4.47 + 0.03, "May: 4.47%", color=DIM, fontsize=11, fontweight='bold')

ax.annotate(f"{yields_[-1]:.2f}%\nnow",
            xy=(dates[-1], yields_[-1]), xytext=(-70, -45), textcoords='offset points',
            color=WHITE, fontsize=15, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=RED, lw=2))

try:
    logo_img = plt.imread(LOGO_PATH)
    logo_box = OffsetImage(logo_img, zoom=0.16)
    ab = AnnotationBbox(logo_box, (SAFE_RIGHT - 0.08, SAFE_TOP - 0.025), xycoords='figure fraction',
                         frameon=False, zorder=10)
    fig.add_artist(ab)
except FileNotFoundError:
    pass

ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
ax.tick_params(colors=TEXT, labelsize=9, rotation=45)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.2f}%'))
for spine in ax.spines.values():
    spine.set_color(GRID)
ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)

fig.text(SAFE_LEFT, SAFE_TOP - 0.035, "10-YR YIELD", color=WHITE, fontsize=27, fontweight='bold')
fig.text(SAFE_LEFT, SAFE_TOP - 0.068, "Treasury  —  May to Sept 2026", color=TEXT, fontsize=13)
fig.text(SAFE_LEFT, SAFE_TOP - 0.105, f"Predictability Score (k=2.0): {score:.1f}%", color=RED,
         fontsize=17, fontweight='bold')

fig.text(SAFE_LEFT, SAFE_BOTTOM - 0.025, "predictability-api.com", color=DIM, fontsize=12, fontweight='bold')

plt.savefig("dgs10_yield_shock.png", dpi=DPI, facecolor=BG)
print("Saved dgs10_yield_shock.png (1080x1920, Shorts-ready)")
print(f"Score: {score:.1f}%  |  May: 4.47%  |  Now: {yields_[-1]:.2f}%")
