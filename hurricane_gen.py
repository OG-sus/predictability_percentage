"""
hurricane_gen.py — Atlantic Hurricane Season FSR
=================================================
NOAA historical storm data (1980-2024), 2-panel YouTube chart.
Left: bar chart with rolling FSR overlay.
Right: score card.

Usage:  python hurricane_gen.py
"""

import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── DATA: NOAA Atlantic Basin Annual Summary 1980-2024 ────────────────────────
# Source: NOAA/NHC historical records (public domain)
# Columns: year, named_storms, hurricanes, major_hurricanes (Cat 3+)
NOAA_DATA = [
    (1980, 11, 9, 2), (1981, 12, 7, 3), (1982,  6, 2, 1), (1983,  4, 3, 1),
    (1984, 12, 5, 1), (1985, 11, 7, 3), (1986,  6, 4, 0), (1987,  7, 3, 1),
    (1988, 12, 5, 3), (1989, 11, 7, 2), (1990, 14, 8, 1), (1991,  8, 4, 2),
    (1992,  7, 4, 1), (1993,  8, 4, 1), (1994,  7, 3, 0), (1995, 19,11, 5),
    (1996, 13, 9, 6), (1997,  8, 3, 1), (1998, 14,10, 3), (1999, 12, 8, 5),
    (2000, 15, 8, 3), (2001, 15, 9, 4), (2002, 12, 4, 2), (2003, 16, 7, 3),
    (2004, 15, 9, 6), (2005, 28,15, 7), (2006, 10, 5, 2), (2007, 15, 6, 2),
    (2008, 16, 8, 5), (2009,  9, 3, 2), (2010, 19,12, 5), (2011, 19, 7, 4),
    (2012, 19,10, 2), (2013,  2, 2, 0), (2014,  8, 6, 2), (2015, 11, 4, 2),
    (2016, 15, 7, 4), (2017, 17,10, 6), (2018, 15, 8, 2), (2019, 18, 6, 3),
    (2020, 30,14, 7), (2021, 21, 7, 4), (2022, 14, 7, 2), (2023, 20, 7, 3),
    (2024, 18,11, 5),
]

YEARS          = [r[0] for r in NOAA_DATA]
NAMED_STORMS   = [r[1] for r in NOAA_DATA]
HURRICANES     = [r[2] for r in NOAA_DATA]
MAJOR          = [r[3] for r in NOAA_DATA]

K      = 1.0
WINDOW = 10       # 10-year rolling FSR
OUT    = "hurricane_gen.png"

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG    = '#080810'
PANEL = '#0d0d1c'
GRID  = '#1a1a2e'
TEXT  = '#d4d4f0'
DIM   = '#5a5a8a'
WHITE = '#f0f0ff'
GREEN = '#00e676'
GOLD  = '#ffca28'
RED   = '#ff5252'

C_NAMED = '#29b6f6'   # blue
C_HURR  = '#ef5350'   # red
C_MAJOR = '#ffca28'   # gold

# ── HELPERS ───────────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 70: return GREEN
    if s >= 45: return GOLD
    return RED

def score_label(s):
    if s >= 70: return 'PREDICTABLE'
    if s >= 45: return 'MODERATE'
    return 'VOLATILE'

def style_ax(ax):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.7)
    ax.grid(axis='x', visible=False)

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart():
    # Compute overall FSR scores
    s_named = calculate_predictability(NAMED_STORMS, k=K)
    s_hurr  = calculate_predictability(HURRICANES,   k=K)
    s_major = calculate_predictability(MAJOR,        k=K)

    # Rolling FSR (10-year window)
    sw_named = calculate_sliding_window(NAMED_STORMS, WINDOW, k=K)
    sw_hurr  = calculate_sliding_window(HURRICANES,   WINDOW, k=K)
    sw_major = calculate_sliding_window(MAJOR,        WINDOW, k=K)

    roll_x     = YEARS[WINDOW - 1:]
    roll_named = [r['score'] for r in sw_named]
    roll_hurr  = [r['score'] for r in sw_hurr]
    roll_major = [r['score'] for r in sw_major]

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(
        2, 2,
        width_ratios=[3.2, 1],
        height_ratios=[1.6, 1],
        hspace=0.38, wspace=0.22,
        left=0.06, right=0.97,
        top=0.87, bottom=0.07,
    )

    ax_bars  = fig.add_subplot(gs[0, 0])   # annual storm counts
    ax_fsr   = fig.add_subplot(gs[1, 0])   # rolling FSR
    ax_score = fig.add_subplot(gs[:, 1])   # score card (full height)

    for ax in [ax_bars, ax_fsr, ax_score]:
        style_ax(ax)

    xs = np.arange(len(YEARS))
    w  = 0.28

    # ── BAR CHART ─────────────────────────────────────────────────────────────
    ax_bars.bar(xs - w,   NAMED_STORMS, w, color=C_NAMED, alpha=0.85, label='Named Storms',     zorder=3)
    ax_bars.bar(xs,       HURRICANES,   w, color=C_HURR,  alpha=0.85, label='Hurricanes',        zorder=3)
    ax_bars.bar(xs + w,   MAJOR,        w, color=C_MAJOR, alpha=0.85, label='Major (Cat 3+)',    zorder=3)

    # Notable seasons annotation
    notable = {2005: 'Katrina', 2017: 'Harvey/Irma', 2020: 'Record 30'}
    for yr, lbl in notable.items():
        if yr in YEARS:
            i = YEARS.index(yr)
            val = NAMED_STORMS[i]
            ax_bars.text(xs[i] - w, val + 0.6, lbl, color=WHITE, fontsize=7.5,
                         ha='center', va='bottom', fontfamily='monospace', alpha=0.8,
                         rotation=0)

    # Season average line
    avg_named = sum(NAMED_STORMS) / len(NAMED_STORMS)
    ax_bars.axhline(avg_named, color=C_NAMED, linewidth=1.0, linestyle='--', alpha=0.4)
    ax_bars.text(len(YEARS) - 0.3, avg_named + 0.4,
                 f'avg {avg_named:.1f}', color=C_NAMED, fontsize=8,
                 fontfamily='monospace', alpha=0.6, ha='right')

    ax_bars.set_xticks(xs[::3])
    ax_bars.set_xticklabels([str(YEARS[i]) for i in range(0, len(YEARS), 3)],
                             fontfamily='monospace', fontsize=9)
    ax_bars.set_xlim(-0.8, len(YEARS) - 0.2)
    ax_bars.set_ylim(0, 36)
    ax_bars.set_ylabel('Storms Per Season', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_bars.set_title('Atlantic Hurricane Season — Annual Activity (1980–2024)',
                      color=WHITE, fontsize=13, fontfamily='monospace', pad=10)

    leg = ax_bars.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                         fontsize=10, loc='upper left', handlelength=1.6)
    for t in leg.get_texts():
        t.set_fontfamily('monospace')

    # ── ROLLING FSR ───────────────────────────────────────────────────────────
    roll_xs = np.arange(WINDOW - 1, len(YEARS))

    for ys, color, label, score in [
        (roll_named, C_NAMED, f'Named Storms  {s_named:.1f}', s_named),
        (roll_hurr,  C_HURR,  f'Hurricanes      {s_hurr:.1f}', s_hurr),
        (roll_major, C_MAJOR, f'Major (Cat3+)  {s_major:.1f}', s_major),
    ]:
        ax_fsr.fill_between(roll_xs, ys, alpha=0.08, color=color)
        ax_fsr.plot(roll_xs, ys, color=color, linewidth=2.0, label=label)
        ax_fsr.scatter([roll_xs[-1]], [ys[-1]], color=color, s=55,
                       zorder=5, edgecolors=BG, linewidths=1.5)
        ax_fsr.text(roll_xs[-1] + 0.3, ys[-1], f'{ys[-1]:.0f}',
                    color=color, fontsize=9, va='center', fontfamily='monospace')

    ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.axhline(45, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.text(0.2, 71.5, 'PREDICTABLE', color=GREEN, fontsize=8, alpha=0.6,
                fontfamily='monospace')
    ax_fsr.text(0.2, 46.5, 'MODERATE',    color=GOLD,  fontsize=8, alpha=0.6,
                fontfamily='monospace')

    ax_fsr.set_xticks(roll_xs[::3])
    ax_fsr.set_xticklabels([str(YEARS[WINDOW - 1 + i * 3]) for i in range(len(roll_xs[::3]))],
                            fontfamily='monospace', fontsize=9)
    ax_fsr.set_xlim(-0.8, len(YEARS) - 0.2)
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_fsr.set_xlabel(f'{WINDOW}-Year Rolling FSR Window  ·  k={K}',
                      color=DIM, fontsize=9, fontfamily='monospace')
    ax_fsr.set_title(f'FSR Predictability Score — {WINDOW}-Year Rolling Window',
                     color=WHITE, fontsize=12, fontfamily='monospace', pad=8)

    leg2 = ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                          fontsize=10, loc='upper right', handlelength=1.6)
    for t in leg2.get_texts():
        t.set_fontfamily('monospace')

    # ── SCORE CARD ────────────────────────────────────────────────────────────
    ax_score.set_xlim(0, 1)
    ax_score.set_ylim(0, 1)
    ax_score.set_xticks([])
    ax_score.set_yticks([])

    ax_score.text(0.5, 0.975, 'FSR VERDICT', ha='center', va='top',
                  fontsize=11, color=DIM, fontfamily='monospace', fontweight='bold')
    ax_score.text(0.5, 0.935, '1980 – 2024', ha='center', va='top',
                  fontsize=9, color=DIM, fontfamily='monospace')

    badges = [
        ('Named Storms', s_named, C_NAMED),
        ('Hurricanes',   s_hurr,  C_HURR),
        ('Major Cat 3+', s_major, C_MAJOR),
    ]
    slot_h  = 0.255
    tops    = [0.88, 0.88 - slot_h, 0.88 - slot_h * 2]

    for (label, score, color), top in zip(badges, tops):
        sc = score_color(score)
        pad = 0.04
        rect = FancyBboxPatch(
            (pad, top - slot_h + pad * 0.5), 1 - pad * 2, slot_h - pad,
            boxstyle='round,pad=0.015',
            facecolor=PANEL, edgecolor=sc, linewidth=2.2, alpha=0.95,
            transform=ax_score.transData, zorder=2,
        )
        ax_score.add_patch(rect)
        mid_y = top - slot_h / 2 + pad * 0.25
        ax_score.text(0.5, mid_y + 0.055, f'{score:.1f}',
                      ha='center', va='center', fontsize=28, fontweight='bold',
                      color=sc, fontfamily='monospace', zorder=3)
        ax_score.text(0.5, mid_y - 0.05, label,
                      ha='center', va='center', fontsize=9, fontweight='bold',
                      color=color, fontfamily='monospace', zorder=3)
        ax_score.text(0.5, mid_y - 0.10, score_label(score),
                      ha='center', va='center', fontsize=8, color=sc,
                      fontfamily='monospace', zorder=3)

    # Season avg stats
    ax_score.text(0.5, 0.025,
                  f'Avg: {avg_named:.1f} named  ·  {sum(HURRICANES)/len(HURRICANES):.1f} hurricanes',
                  ha='center', fontsize=8, color=DIM, fontfamily='monospace')

    # ── HEADER ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             'ATLANTIC HURRICANE SEASON  —  IS IT PREDICTABLE?',
             ha='center', fontsize=20, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.930,
             'Named Storms  ·  Hurricanes  ·  Major (Cat 3+)  ·  FSR Predictability Score™  '
             '·  Data: NOAA/NHC  ·  Season starts June 1',
             ha='center', fontsize=10, color=DIM, fontfamily='monospace')

    ts = datetime.now().strftime('%Y-%m-%d')
    fig.text(0.97, 0.012,
             f'Data: NOAA National Hurricane Center  ·  {ts}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    plt.savefig(OUT, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f'Saved: {OUT}')
    plt.show()

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Hurricane Season FSR — YouTube Chart')
    print('=' * 40)

    s_named = calculate_predictability(NAMED_STORMS, k=K)
    s_hurr  = calculate_predictability(HURRICANES,   k=K)
    s_major = calculate_predictability(MAJOR,        k=K)

    print(f'  Named Storms  FSR: {s_named:.1f}  [{score_label(s_named)}]')
    print(f'  Hurricanes    FSR: {s_hurr:.1f}  [{score_label(s_hurr)}]')
    print(f'  Major Cat3+   FSR: {s_major:.1f}  [{score_label(s_major)}]')
    print()
    print('Building chart...')
    build_chart()
