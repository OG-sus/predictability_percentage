#!/usr/bin/env python3
"""GPU Market Price Trends 2022-2025 — NVIDIA / AMD / Intel"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
from datetime import datetime

# ── PALETTE ──────────────────────────────────────────────────────────────────
BG      = '#080810'
PANEL   = '#0e0e1a'
GRID    = '#1a1a2e'
NV_C    = '#76b900'   # NVIDIA green
AM_C    = '#ff3d00'   # AMD red-orange
IT_C    = '#29a8ff'   # Intel blue
TEXT    = '#d4d4e8'
DIM     = '#5a5a7a'
WHITE   = '#f0f0ff'

def d(y, m): return datetime(y, m, 1)

# ── DATA — avg street/ebay price (USD) for flagship tier per brand ─────────
# NVIDIA: RTX 3080 (Jan22–Dec23) → RTX 4080 (Jan24–Dec24) → RTX 5080 (Jan25+) market avg
nvidia = [
    d(2022,1),1060, d(2022,2),1020, d(2022,3),970,  d(2022,4),895,
    d(2022,5),800,  d(2022,6),705,  d(2022,7),640,  d(2022,8),585,
    d(2022,9),553,  d(2022,10),528, d(2022,11),508, d(2022,12),490,
    d(2023,1),473,  d(2023,2),460,  d(2023,3),448,  d(2023,4),460,
    d(2023,5),482,  d(2023,6),518,  d(2023,7),558,  d(2023,8),595,
    d(2023,9),632,  d(2023,10),672, d(2023,11),712, d(2023,12),748,
    d(2024,1),772,  d(2024,2),808,  d(2024,3),842,  d(2024,4),868,
    d(2024,5),892,  d(2024,6),912,  d(2024,7),932,  d(2024,8),950,
    d(2024,9),962,  d(2024,10),978, d(2024,11),998, d(2024,12),1022,
    d(2025,1),1125, d(2025,2),1198, d(2025,3),1242, d(2025,4),1268,
    d(2025,5),1292,
]

# AMD: RX 6800 XT (Jan22–Oct22) → RX 7900 XTX (Nov22–Feb25) → RX 9070 XT (Mar25+)
amd = [
    d(2022,1),828,  d(2022,2),798,  d(2022,3),752,  d(2022,4),682,
    d(2022,5),598,  d(2022,6),522,  d(2022,7),472,  d(2022,8),438,
    d(2022,9),412,  d(2022,10),388, d(2022,11),372, d(2022,12),362,
    d(2023,1),352,  d(2023,2),346,  d(2023,3),340,  d(2023,4),348,
    d(2023,5),362,  d(2023,6),378,  d(2023,7),396,  d(2023,8),414,
    d(2023,9),432,  d(2023,10),452, d(2023,11),470, d(2023,12),488,
    d(2024,1),498,  d(2024,2),508,  d(2024,3),518,  d(2024,4),522,
    d(2024,5),526,  d(2024,6),529,  d(2024,7),531,  d(2024,8),533,
    d(2024,9),529,  d(2024,10),523, d(2024,11),518, d(2024,12),512,
    d(2025,1),506,  d(2025,2),516,  d(2025,3),542,  d(2025,4),552,
    d(2025,5),558,
]

# Intel: Arc A770 launched Sep 2022 ($329 MSRP) → Arc B580 (Nov 2024, $249 MSRP)
intel = [
    d(2022,9),338,  d(2022,10),326, d(2022,11),315, d(2022,12),306,
    d(2023,1),297,  d(2023,2),289,  d(2023,3),281,  d(2023,4),275,
    d(2023,5),269,  d(2023,6),264,  d(2023,7),259,  d(2023,8),255,
    d(2023,9),251,  d(2023,10),248, d(2023,11),245, d(2023,12),244,
    d(2024,1),241,  d(2024,2),238,  d(2024,3),235,  d(2024,4),232,
    d(2024,5),229,  d(2024,6),226,  d(2024,7),223,  d(2024,8),220,
    d(2024,9),218,  d(2024,10),216, d(2024,11),262, d(2024,12),274,
    d(2025,1),270,  d(2025,2),274,  d(2025,3),271,  d(2025,4),268,
    d(2025,5),265,
]

def unzip(flat): return flat[0::2], flat[1::2]
nv_x, nv_y = unzip(nvidia)
am_x, am_y = unzip(amd)
it_x, it_y = unzip(intel)

# ── FIGURE ───────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(18, 9.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(PANEL)

# ── ERA SHADING ───────────────────────────────────────────────────────────────
eras = [
    (d(2022,1), d(2022,5),  '#ff8800', 0.07),
    (d(2022,5), d(2023,3),  '#cc2200', 0.08),
    (d(2023,3), d(2024,1),  '#2266cc', 0.06),
    (d(2024,1), d(2025,6),  '#44aa00', 0.07),
]
for x0, x1, c, a in eras:
    ax.axvspan(x0, x1, facecolor=c, alpha=a, zorder=0)

# ── AREA FILLS ────────────────────────────────────────────────────────────────
ax.fill_between(nv_x, nv_y, 100, alpha=0.07, color=NV_C, zorder=1)
ax.fill_between(am_x, am_y, 100, alpha=0.07, color=AM_C, zorder=1)
ax.fill_between(it_x, it_y, 100, alpha=0.06, color=IT_C, zorder=1)

# ── GLOW LINES ────────────────────────────────────────────────────────────────
def glow_plot(ax, xs, ys, color, lw=2.5, label='', zorder=5):
    ax.plot(xs, ys, color=color, alpha=0.08, linewidth=lw*5,   zorder=zorder-1, solid_capstyle='round')
    ax.plot(xs, ys, color=color, alpha=0.20, linewidth=lw*2.5, zorder=zorder,   solid_capstyle='round')
    ax.plot(xs, ys, color=color, alpha=0.60, linewidth=lw*1.3, zorder=zorder+1, solid_capstyle='round')
    ax.plot(xs, ys, color=color, linewidth=lw,                 zorder=zorder+2, label=label, solid_capstyle='round')
    # endpoint dot
    ax.scatter([xs[-1]], [ys[-1]], color=color, s=55, zorder=zorder+3, edgecolors=BG, linewidths=1.5)

glow_plot(ax, nv_x, nv_y, NV_C, lw=2.8, label='NVIDIA  (RTX 3080 → 4080 → 5080 tier)',  zorder=8)
glow_plot(ax, am_x, am_y, AM_C, lw=2.5, label='AMD     (RX 6800 XT → 7900 XTX → 9070 XT)', zorder=7)
glow_plot(ax, it_x, it_y, IT_C, lw=2.2, label='Intel   (Arc A770 → B580)',                 zorder=6)

# ── EVENT ANNOTATIONS ─────────────────────────────────────────────────────────
events = [
    # (x_date, y_data, label, y_offset, color, ha)
    (d(2022,1),  1060, 'Mining\nPeak',         +105, NV_C,     'center'),
    (d(2022,5),  800,  'LUNA\nCrash',           -110, '#ff9900', 'center'),
    (d(2022,9),  553,  'ETH\nMerge',            -105, DIM,      'center'),
    (d(2023,3),  448,  'Inventory\nGlut Floor', -110, AM_C,     'center'),
    (d(2023,5),  482,  'ChatGPT /\nAI Narrative',+100, NV_C,    'center'),
    (d(2024,11), 262,  'Arc B580\nLaunch',       +90, IT_C,     'center'),
    (d(2025,1),  1125, 'RTX 5000\nLaunch',      +100, NV_C,     'center'),
]

for xd, yv, label, yoff, col, ha in events:
    ax.annotate(
        label,
        xy=(xd, yv),
        xytext=(xd, yv + yoff),
        ha=ha, va='bottom' if yoff > 0 else 'top',
        fontsize=8.2, color=col, fontfamily='monospace',
        arrowprops=dict(arrowstyle='->', color=col, lw=1.1, alpha=0.75,
                        connectionstyle='arc3,rad=0.0'),
        bbox=dict(boxstyle='round,pad=0.35', facecolor='#080810',
                  edgecolor=col, alpha=0.92, linewidth=0.9),
        zorder=20,
    )

# ── ERA LABELS (top band) ─────────────────────────────────────────────────────
era_meta = [
    (d(2022,1), d(2022,5),  '▲ MINING PEAK',    '#ff9900'),
    (d(2022,5), d(2023,3),  '▼ CRASH & GLUT',   '#ff4422'),
    (d(2023,3), d(2024,1),  '↗ RECOVERY',        '#5599ff'),
    (d(2024,1), d(2025,6),  '▲ AI PREMIUM ERA',  NV_C),
]
Y_ERA = 1365
for x0, x1, label, col in era_meta:
    mid = x0 + (x1 - x0) / 2
    ax.text(mid, Y_ERA, label, ha='center', va='center',
            fontsize=9, color=col, fontfamily='monospace', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor=BG,
                      edgecolor=col, alpha=0.9, linewidth=0.8),
            zorder=15)
    ax.axvline(x0, color=GRID, linewidth=0.7, linestyle='--', alpha=0.6, zorder=3)
ax.axvline(d(2025,6), color=GRID, linewidth=0.7, linestyle='--', alpha=0.6, zorder=3)

# ── AXIS FORMATTING ───────────────────────────────────────────────────────────
ax.set_xlim(d(2022,1), d(2025,6))
ax.set_ylim(130, 1430)

ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'${int(v):,}'))
ax.yaxis.set_major_locator(mticker.MultipleLocator(150))
ax.yaxis.set_minor_locator(mticker.MultipleLocator(50))

ax.tick_params(axis='both', colors=TEXT, labelsize=9.5, length=4)
ax.tick_params(axis='x',    rotation=35)
ax.tick_params(axis='y',    which='minor', length=2, color=GRID)

for spine in ax.spines.values():
    spine.set_edgecolor(GRID)
    spine.set_linewidth(0.8)

ax.grid(axis='y', color=GRID, linestyle='-',  linewidth=0.6, alpha=0.9, zorder=2)
ax.grid(axis='x', color=GRID, linestyle=':', linewidth=0.4, alpha=0.5, zorder=2)
ax.grid(axis='y', which='minor', color=GRID, linestyle=':', linewidth=0.3, alpha=0.4, zorder=2)

# ── TITLES ────────────────────────────────────────────────────────────────────
fig.suptitle('GPU Market Price Trends  ·  2022 – 2025',
             fontsize=23, fontweight='bold', color=WHITE,
             fontfamily='monospace', y=0.975)
ax.set_title('Avg. Street Prices for Flagship Discrete GPUs   |   Mining Boom → Inventory Crash → AI Premium',
             fontsize=10.5, color=DIM, fontfamily='monospace', pad=11)
ax.set_ylabel('Average Street Price (USD)', color=TEXT, fontsize=11, labelpad=14)

# ── LEGEND ────────────────────────────────────────────────────────────────────
legend = ax.legend(
    loc='upper left', frameon=True, fancybox=False,
    facecolor='#0c0c18', edgecolor=GRID,
    labelcolor=TEXT, fontsize=10.5,
    handlelength=2.8, handletextpad=0.8,
    borderpad=0.9, labelspacing=0.6,
)
legend.get_frame().set_linewidth(0.9)
for text in legend.get_texts():
    text.set_fontfamily('monospace')

# ── FOOTNOTE ──────────────────────────────────────────────────────────────────
fig.text(0.995, 0.012,
         'Estimated avg. market/street prices (USD)  ·  Sources: eBay sold listings, CamelCamelCamel, GPU price trackers  ·  Historical approximation',
         ha='right', va='bottom', fontsize=7.2, color='#333348',
         fontfamily='monospace')

plt.tight_layout(rect=[0, 0.01, 1, 0.965])
out = 'gpu_price_trends.png'
plt.savefig(out, dpi=180, facecolor=BG, bbox_inches='tight')
plt.show()
print(f"Saved: {out}")
