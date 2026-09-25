#!/usr/bin/env python3
"""PS5 Price Shock — real dated Sony price announcements, 2025-2026.

PS5 Disc Edition, US MSRP. Step series reflects actual announced change
dates, flat between them (no interpolation - these are real step changes,
not a continuously moving price):
  - Launch (Nov 2020): $499.99
  - Aug 20, 2025: Sony raises to $549.99, citing new tariffs
  - Apr 2, 2026: Sony raises to $649.99, citing DRAM/memory cost crisis
  - Aug 21, 2026: Sony reverses the April hike, back to $549.99
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
PS_C  = '#0070d1'   # PlayStation blue
TEXT  = '#d4d4e8'
DIM   = '#5a5a7a'
WHITE = '#f0f0ff'
RED   = '#ff3d3d'
GREEN = '#3dff8f'

def d(y, m): return datetime(y, m, 1)

dates = [d(2025,1), d(2025,2), d(2025,3), d(2025,4), d(2025,5), d(2025,6), d(2025,7),
         d(2025,8), d(2025,9), d(2025,10), d(2025,11), d(2025,12),
         d(2026,1), d(2026,2), d(2026,3), d(2026,4), d(2026,5), d(2026,6), d(2026,7),
         d(2026,8), d(2026,9)]
prices = [499.99]*7 + [549.99]*8 + [649.99]*4 + [549.99]*2

score = calculate_predictability(prices, k=2.0)

# YouTube Shorts UI covers the outer frame (like/comment/share column on the
# right, caption/handle/progress bar at the bottom, account switcher up top).
# Everything meaningful - logo, text, plotted data - has to sit inside this
# inner safe box, not just inset from the true pixel edge.
SAFE_LEFT, SAFE_RIGHT = 0.075, 0.80   # ~80px / ~215px margins on a 1080-wide frame
SAFE_TOP, SAFE_BOTTOM = 0.88, 0.205   # ~230px top / ~395px bottom margins on 1920-tall

fig = plt.figure(figsize=(SHORTS_W_IN, SHORTS_H_IN), facecolor=BG, dpi=DPI)
ax = fig.add_axes([SAFE_LEFT + 0.09, SAFE_BOTTOM + 0.02, SAFE_RIGHT - (SAFE_LEFT + 0.09) - 0.01, 0.44])
ax.set_facecolor(PANEL)

ax.step(dates, prices, where='post', color=PS_C, linewidth=3.5, zorder=5)
ax.plot(dates, prices, 'o', color=PS_C, markersize=6,
        markerfacecolor=WHITE, markeredgecolor=PS_C, markeredgewidth=1.5, zorder=6)
ax.fill_between(dates, prices, 480, step='post', color=PS_C, alpha=0.10)
ax.set_xlim(dates[0], d(2026, 10))  # padding on the right so the last point isn't flush with the axes edge

ax.axhline(499.99, color=DIM, linestyle='--', linewidth=1.2, alpha=0.6)
ax.text(dates[0], 499.99 + 10, "Launch: $499.99", color=DIM, fontsize=11, fontweight='bold')

# Callout on the April 2026 spike to $649.99
ax.annotate("$649.99\nDRAM crisis hike",
            xy=(d(2026,4), 649.99), xytext=(-70, 22), textcoords='offset points',
            color=WHITE, fontsize=13, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=RED, lw=2))

# Callout on the August 2026 reversal back down - offset kept left/down so it
# stays inside the safe box instead of drifting toward the right-edge UI column.
ax.annotate("$549.99\nSony reverses it",
            xy=(d(2026,8), 549.99), xytext=(-100, -50), textcoords='offset points',
            color=WHITE, fontsize=13, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color=GREEN, lw=2))

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

fig.text(SAFE_LEFT, SAFE_TOP - 0.035, "PS5 PRICE", color=WHITE, fontsize=27, fontweight='bold')
fig.text(SAFE_LEFT, SAFE_TOP - 0.068, "Disc Edition  —  Jan 2025 to Sept 2026", color=TEXT, fontsize=13)
fig.text(SAFE_LEFT, SAFE_TOP - 0.105, f"Predictability Score (k=2.0): {score:.1f}%", color=RED,
         fontsize=17, fontweight='bold')

fig.text(SAFE_LEFT, SAFE_BOTTOM - 0.025, "predictability-api.com", color=DIM, fontsize=12, fontweight='bold')

plt.savefig("ps5_price_shock.png", dpi=DPI, facecolor=BG)
print("Saved ps5_price_shock.png (1080x1920, Shorts-ready)")
print(f"Score: {score:.1f}%  |  Launch: $499.99  |  Peak: $649.99  |  Now: $549.99")
