"""
inflation_gen.py — US Inflation (CPI) FSR Chart
=================================================
Pulls CPI data from BLS public API (no key needed).
Shows YoY inflation rate + MoM change + FSR rolling score.
YouTube-ready 1920x1080 dark chart.

Usage:  python inflation_gen.py
"""

import json
import urllib.request
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── CONFIG ────────────────────────────────────────────────────────────────────
WINDOW = 6
K      = 1.5
OUT    = 'inflation_gen.png'

SERIES_CPI = 'CUSR0000SA0'   # CPI-U All Items, seasonally adjusted

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
CYAN  = '#29b6f6'
ORANGE = '#ff9800'

# ── FETCH ─────────────────────────────────────────────────────────────────────
BLS_URL = 'https://api.bls.gov/publicAPI/v1/timeseries/data/'

def fetch_bls(series_id, label=''):
    payload = json.dumps({'seriesid': [series_id]}).encode()
    req = urllib.request.Request(
        BLS_URL, data=payload,
        headers={'Content-Type': 'application/json', 'User-Agent': 'FSR-Research/1.0'}
    )
    print(f'  Fetching {label or series_id}...')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        series = list(reversed(data['Results']['series'][0]['data']))
        pairs  = [(f"{s['year']}-{s['period'].replace('M','')}", s['value']) for s in series]
        pairs  = [(d, v) for d, v in pairs if v not in ('-', 'N/A', '')]
        dates  = [d for d, _ in pairs]
        vals   = [float(v) for _, v in pairs]
        print(f'    {len(vals)} months  |  latest: {vals[-1]:.3f}  ({dates[-1]})')
        return dates, vals
    except Exception as e:
        print(f'    FAILED: {e}')
        return [], []

# ── HELPERS ───────────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 70: return GREEN
    if s >= 45: return GOLD
    return RED

def score_label(s):
    if s >= 70: return 'CONSISTENT'
    if s >= 45: return 'MODERATE'
    return 'VOLATILE'

def style_ax(ax):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.7)
    ax.grid(axis='x', color=GRID, linewidth=0.3, alpha=0.35)

def glow_plot(ax, xs, ys, color, lw=2.2, label='', zorder=5):
    ax.fill_between(xs, ys, alpha=0.07, color=color, zorder=zorder - 2)
    ax.plot(xs, ys, color=color, alpha=0.12, linewidth=lw * 5, zorder=zorder - 1, solid_capstyle='round')
    ax.plot(xs, ys, color=color, alpha=0.30, linewidth=lw * 2, zorder=zorder,     solid_capstyle='round')
    ax.plot(xs, ys, color=color, linewidth=lw,                 zorder=zorder + 1, solid_capstyle='round', label=label)
    ax.scatter([xs[-1]], [ys[-1]], color=color, s=55, zorder=zorder + 2, edgecolors=BG, linewidths=1.5)

def to_dt(date_strs):
    return [datetime.strptime(d + '-01', '%Y-%m-%d') for d in date_strs]

def apply_date_axis(ax, x_min, x_max):
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.set_xlim(x_min, x_max)
    plt.setp(ax.get_xticklabels(), rotation=20, ha='right',
             fontfamily='monospace', fontsize=8, color=TEXT)

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart(cpi_dates, cpi_vals):
    # YoY inflation rate (% change vs 12 months ago)
    yoy_vals  = [(cpi_vals[i] - cpi_vals[i-12]) / cpi_vals[i-12] * 100
                 for i in range(12, len(cpi_vals))]
    yoy_dates = cpi_dates[12:]

    # MoM change
    mom_vals  = [(cpi_vals[i] - cpi_vals[i-1]) / cpi_vals[i-1] * 100
                 for i in range(1, len(cpi_vals))]
    mom_dates = cpi_dates[1:]

    s_yoy = calculate_predictability(yoy_vals, k=K) if len(yoy_vals) >= 2 else 0
    s_mom = calculate_predictability(mom_vals, k=K) if len(mom_vals) >= 2 else 0

    dt_yoy = to_dt(yoy_dates)
    dt_mom = to_dt(mom_dates)
    x_min  = dt_yoy[0]
    x_max  = dt_yoy[-1]

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(
        3, 2,
        width_ratios=[3.2, 1],
        height_ratios=[1.1, 1.1, 1.3],
        hspace=0.55, wspace=0.22,
        left=0.06, right=0.97,
        top=0.87, bottom=0.16,
    )

    ax_yoy = fig.add_subplot(gs[0, 0])
    ax_mom = fig.add_subplot(gs[1, 0])
    ax_fsr = fig.add_subplot(gs[2, 0])
    ax_sc  = fig.add_subplot(gs[:, 1])

    for ax in [ax_yoy, ax_mom, ax_fsr, ax_sc]:
        style_ax(ax)

    # ── YoY INFLATION RATE ────────────────────────────────────────────────────
    # Color the line: red above 3%, gold 2-3%, green below 2% (Fed target)
    glow_plot(ax_yoy, dt_yoy, yoy_vals, ORANGE, lw=2.2,
              label=f'YoY Inflation Rate  [{s_yoy:.1f}]')
    ax_yoy.axhline(2.0, color=GREEN, linewidth=1.0, linestyle='--', alpha=0.6,
                   label='Fed 2% Target')
    ax_yoy.axhline(3.0, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.5)
    ax_yoy.text(dt_yoy[0], 2.15, '2% Fed Target', color=GREEN, fontsize=8,
                fontfamily='monospace', alpha=0.7)

    # Annotate the latest value
    latest_yoy = yoy_vals[-1]
    ax_yoy.scatter([dt_yoy[-1]], [latest_yoy], color=RED if latest_yoy > 3 else GOLD,
                   s=80, zorder=10, edgecolors=BG, linewidths=1.5)
    ax_yoy.text(dt_yoy[-1], latest_yoy + 0.15, f'{latest_yoy:.2f}%',
                color=RED if latest_yoy > 3 else GOLD, fontsize=10,
                fontweight='bold', fontfamily='monospace', ha='right')

    ax_yoy.set_ylabel('YoY Change (%)', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_yoy.set_title('CPI Inflation Rate — Year Over Year', color=WHITE, fontsize=12,
                     fontfamily='monospace', pad=8)
    apply_date_axis(ax_yoy, x_min, x_max)
    leg = ax_yoy.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                        fontsize=9, loc='upper left')
    for t in leg.get_texts(): t.set_fontfamily('monospace')

    # ── MoM CHANGE BARS ───────────────────────────────────────────────────────
    # Only show MoM bars that overlap with YoY date range
    dt_mom_trim = [d for d in dt_mom if d >= x_min]
    mom_trim    = mom_vals[len(mom_vals) - len(dt_mom_trim):]
    colors_bar  = [RED if v > 0.3 else GREEN if v <= 0 else GOLD for v in mom_trim]

    ax_mom.bar(dt_mom_trim, mom_trim, color=colors_bar, alpha=0.80, width=20)
    ax_mom.axhline(0, color=DIM, linewidth=0.8, alpha=0.5)
    ax_mom.set_ylabel('MoM Change (%)', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_mom.set_title('CPI Month-Over-Month Change', color=WHITE, fontsize=12,
                     fontfamily='monospace', pad=8)
    apply_date_axis(ax_mom, x_min, x_max)
    # Add FSR score label in corner
    ax_mom.text(0.99, 0.97, f'FSR: {s_mom:.1f}  [{score_label(s_mom)}]',
                transform=ax_mom.transAxes, ha='right', va='top',
                color=score_color(s_mom), fontsize=10, fontfamily='monospace',
                fontweight='bold')

    # ── ROLLING FSR ───────────────────────────────────────────────────────────
    for vals, dt_dates, color, label in [
        (yoy_vals, dt_yoy, ORANGE, f'YoY Inflation FSR  {s_yoy:.1f}'),
        (mom_trim,  dt_mom_trim, CYAN,   f'MoM CPI FSR        {s_mom:.1f}'),
    ]:
        if len(vals) < WINDOW + 1:
            continue
        sw   = calculate_sliding_window(vals, WINDOW, k=K)
        sw_y = [r['score'] for r in sw]
        sw_x = dt_dates[WINDOW - 1:]
        ax_fsr.fill_between(sw_x, sw_y, alpha=0.08, color=color)
        ax_fsr.plot(sw_x, sw_y, color=color, linewidth=2.0, label=label)
        ax_fsr.scatter([sw_x[-1]], [sw_y[-1]], color=color, s=55,
                       zorder=5, edgecolors=BG, linewidths=1.5)
        ax_fsr.text(sw_x[-1], sw_y[-1] + 3, f'{sw_y[-1]:.0f}',
                    color=color, fontsize=9, va='bottom', ha='right',
                    fontfamily='monospace')

    fsr_x_min = dt_yoy[WINDOW - 1]   # start where FSR data actually begins
    ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.axhline(45, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.text(fsr_x_min, 71.5, 'CONSISTENT', color=GREEN, fontsize=8,
                alpha=0.6, fontfamily='monospace')
    ax_fsr.text(fsr_x_min, 46.5, 'MODERATE',   color=GOLD,  fontsize=8,
                alpha=0.6, fontfamily='monospace')
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_fsr.set_title(f'FSR Predictability Score — {WINDOW}-Month Rolling Window',
                     color=WHITE, fontsize=12, fontfamily='monospace', pad=8)
    apply_date_axis(ax_fsr, fsr_x_min, x_max)
    leg3 = ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                         fontsize=9, loc='upper right')
    for t in leg3.get_texts(): t.set_fontfamily('monospace')

    # ── SCORE CARD ────────────────────────────────────────────────────────────
    ax_sc.set_xlim(0, 1); ax_sc.set_ylim(0, 1)
    ax_sc.set_xticks([]); ax_sc.set_yticks([])

    ax_sc.text(0.5, 0.975, 'FSR VERDICT', ha='center', va='top',
               fontsize=11, color=DIM, fontfamily='monospace', fontweight='bold')
    ax_sc.text(0.5, 0.935, 'Inflation Predictability', ha='center', va='top',
               fontsize=9, color=DIM, fontfamily='monospace')

    badges = [
        ('YoY Rate',  s_yoy, ORANGE),
        ('MoM CPI',   s_mom, CYAN),
    ]
    slot_h = 0.22
    tops   = [0.88, 0.88 - slot_h]

    for (label, score, color), top in zip(badges, tops):
        sc  = score_color(score)
        pad = 0.04
        rect = FancyBboxPatch(
            (pad, top - slot_h + pad * 0.5), 1 - pad * 2, slot_h - pad,
            boxstyle='round,pad=0.015',
            facecolor=PANEL, edgecolor=sc, linewidth=2.2, alpha=0.95,
            transform=ax_sc.transData, zorder=2,
        )
        ax_sc.add_patch(rect)
        mid_y = top - slot_h / 2 + pad * 0.25
        ax_sc.text(0.5, mid_y + 0.055, f'{score:.1f}', ha='center', va='center',
                   fontsize=28, fontweight='bold', color=sc, fontfamily='monospace', zorder=3)
        ax_sc.text(0.5, mid_y - 0.05, label, ha='center', va='center',
                   fontsize=9, fontweight='bold', color=color, fontfamily='monospace', zorder=3)
        ax_sc.text(0.5, mid_y - 0.10, score_label(score), ha='center', va='center',
                   fontsize=8, color=sc, fontfamily='monospace', zorder=3)

    # Current rate callout
    ax_sc.text(0.5, 0.30, '3-YEAR HIGH', ha='center', fontsize=10,
               color=RED, fontfamily='monospace', fontweight='bold')
    ax_sc.text(0.5, 0.23, f'{latest_yoy:.2f}%', ha='center', fontsize=26,
               fontweight='bold', color=RED, fontfamily='monospace')
    ax_sc.text(0.5, 0.16, 'CPI Year-Over-Year', ha='center', fontsize=8,
               color=DIM, fontfamily='monospace')
    ax_sc.text(0.5, 0.09, f'Fed Target: 2.0%', ha='center', fontsize=8,
               color=GREEN, fontfamily='monospace', alpha=0.8)
    ax_sc.text(0.5, 0.03, f'Above target by {latest_yoy - 2.0:.2f}%', ha='center',
               fontsize=8, color=GOLD, fontfamily='monospace')

    # ── HEADER ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             'INFLATION HITS 3-YEAR HIGH — HOW PREDICTABLE HAS IT BEEN?',
             ha='center', fontsize=18, fontweight='bold', color=WHITE,
             fontfamily='monospace')
    fig.text(0.5, 0.930,
             'CPI YoY Rate  ·  Month-Over-Month Change  ·  FSR Predictability Score™  ·  Data: BLS.gov',
             ha='center', fontsize=10, color=DIM, fontfamily='monospace')

    ts_str = datetime.now().strftime('%Y-%m-%d')
    fig.text(0.97, 0.005,
             f'Data: bls.gov  ·  {ts_str}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    plt.savefig(OUT, dpi=100, facecolor=BG, bbox_inches='tight')
    plt.close()
    print(f'\nSaved: {OUT}')

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Inflation FSR — YouTube Chart')
    print('=' * 40)

    cpi_dates, cpi_vals = fetch_bls(SERIES_CPI, 'CPI-U All Items')

    if not cpi_vals:
        print('\nERROR: Could not fetch BLS data.')
        exit(1)

    print(f'\n  YoY Inflation FSR: calculating...')
    print('\nBuilding chart...')
    build_chart(cpi_dates, cpi_vals)
