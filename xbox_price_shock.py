#!/usr/bin/env python3
"""Xbox Price Shock — real dated Microsoft price changes, 2025-2026.

US MSRP. Step series reflects actual announced change dates, flat between
them (no interpolation - these are real step changes):
  Series X (1TB disc)        Series S (512GB)
  - Launch Nov 2020: $499.99   $299.99
  - May 1, 2025:     $599.99   $379.99   (tariffs)
  - Oct 3, 2025:     $649.99   $399.99   (tariffs, US only)
  - Aug 1, 2026:     $799.99   $499.99   (memory/storage costs up 2.5x - DRAM crisis)

Sources: Xbox Wire (news.xbox.com, 2026-06-25), CNBC 2026-06-25,
Tom's Hardware / Game Developer (Oct 2025), Windows Central (Aug 2026).

The story: consoles normally get CHEAPER late in a generation. Year 6 of
this one, both Xboxes cost 60%+ more than at launch.
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
XB_C  = '#107c10'   # Xbox green
XB_S  = '#c8c8d8'   # Series S (the white console)
TEXT  = '#d4d4e8'
DIM   = '#5a5a7a'
WHITE = '#f0f0ff'
RED   = '#ff3d3d'

def d(y, m): return datetime(y, m, 1)

dates = [d(2025,1), d(2025,2), d(2025,3), d(2025,4), d(2025,5), d(2025,6), d(2025,7),
         d(2025,8), d(2025,9), d(2025,10), d(2025,11), d(2025,12),
         d(2026,1), d(2026,2), d(2026,3), d(2026,4), d(2026,5), d(2026,6), d(2026,7),
         d(2026,8), d(2026,9)]
series_x = [499.99]*4 + [599.99]*5 + [649.99]*10 + [799.99]*2
series_s = [299.99]*4 + [379.99]*5 + [399.99]*10 + [499.99]*2

score_x = calculate_predictability(series_x, k=2.0)
score_s = calculate_predictability(series_s, k=2.0)

# Same Shorts safe box as ps5_price_shock.py - the right-side like/comment
# column and bottom caption area cover the outer frame.
SAFE_LEFT, SAFE_RIGHT = 0.075, 0.80
SAFE_TOP, SAFE_BOTTOM = 0.88, 0.205

fig = plt.figure(figsize=(SHORTS_W_IN, SHORTS_H_IN), facecolor=BG, dpi=DPI)
ax = fig.add_axes([SAFE_LEFT + 0.09, SAFE_BOTTOM + 0.02, SAFE_RIGHT - (SAFE_LEFT + 0.09) - 0.01, 0.49])
ax.set_facecolor(PANEL)

for prices, color, label in ((series_x, XB_C, "Series X"), (series_s, XB_S, "Series S")):
    ax.step(dates, prices, where='post', color=color, linewidth=3.5, zorder=5, label=label)
    ax.plot(dates, prices, 'o', color=color, markersize=6,
            markerfacecolor=WHITE, markeredgecolor=color, markeredgewidth=1.5, zorder=6)
    ax.fill_between(dates, prices, 250, step='post', color=color, alpha=0.08)
ax.set_xlim(dates[0], d(2026, 10))  # right padding so the last point isn't flush
ax.set_ylim(250, 880)

# Launch prices as the "should be getting cheaper" reference
ax.axhline(499.99, color=XB_C, linestyle='--', linewidth=1.2, alpha=0.5)
ax.text(d(2025,11), 499.99 + 12, "X launch: $499.99", color=XB_C, fontsize=11, fontweight='bold', alpha=0.9)
ax.axhline(299.99, color=DIM, linestyle='--', linewidth=1.2, alpha=0.6)
ax.text(d(2025,11), 299.99 + 12, "S launch: $299.99", color=DIM, fontsize=11, fontweight='bold')

# Callouts kept left of the final points so they stay inside the safe box.
ax.annotate("$799.99\n+60% since launch",
            xy=(d(2026,8), 799.99), xytext=(-105, 14), textcoords='offset points',
            color=WHITE, fontsize=13, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=RED, lw=2))
ax.annotate("$499.99\n+67%",
            xy=(d(2026,8), 499.99), xytext=(-70, -62), textcoords='offset points',
            color=WHITE, fontsize=13, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=RED, lw=2))

legend = ax.legend(loc='upper left', bbox_to_anchor=(0.0, 0.93), facecolor=PANEL, edgecolor=GRID,
                   labelcolor=TEXT, fontsize=12)

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
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.0f}'))
for spine in ax.spines.values():
    spine.set_color(GRID)
ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)

fig.text(SAFE_LEFT, SAFE_TOP - 0.035, "XBOX PRICE", color=WHITE, fontsize=27, fontweight='bold')
fig.text(SAFE_LEFT, SAFE_TOP - 0.068, "Series X & S  —  Jan 2025 to Sept 2026", color=TEXT, fontsize=13)
fig.text(SAFE_LEFT, SAFE_TOP - 0.105, f"Predictability Score (k=2.0): {score_x:.1f}%", color=RED,
         fontsize=17, fontweight='bold')
fig.text(SAFE_LEFT, SAFE_TOP - 0.132, "Year 6 of the generation — when consoles usually get CHEAPER",
         color=DIM, fontsize=11)

fig.text(SAFE_LEFT, SAFE_BOTTOM - 0.025, "predictability-api.com", color=DIM, fontsize=12, fontweight='bold')

plt.savefig("xbox_price_shock.png", dpi=DPI, facecolor=BG)
print("Saved xbox_price_shock.png (1080x1920, Shorts-ready)")
print(f"Series X score: {score_x:.1f}%  |  $499.99 -> $799.99 (+60%)")
print(f"Series S score: {score_s:.1f}%  |  $299.99 -> $499.99 (+67%)")
