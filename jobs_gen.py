"""
jobs_gen.py — US Jobs Report FSR Chart
=======================================
Pulls Unemployment Rate + Nonfarm Payrolls from BLS public API (no key needed).
Runs FSR sliding window. YouTube-ready 1920x1080 dark chart.

Usage:  python jobs_gen.py
"""

import json
import urllib.request
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── CONFIG ────────────────────────────────────────────────────────────────────
WINDOW       = 6       # 6-month rolling FSR
K            = 1.5
OUT          = 'jobs_gen.png'
ANALYST_EST  = 85  # consensus forecast in PAYEMS units (thousands) — 85 = 85,000 jobs

# BLS series IDs (no API key — last 10 years, monthly)
SERIES_UNRATE = 'LNS14000000'   # Unemployment rate %
SERIES_PAYEMS = 'CES0000000001' # Nonfarm payrolls, thousands of persons

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
PINK  = '#f06292'

# ── FETCH ─────────────────────────────────────────────────────────────────────
BLS_URL = 'https://api.bls.gov/publicAPI/v1/timeseries/data/'

def fetch_bls(series_id, label=''):
    payload = json.dumps({'seriesid': [series_id]}).encode()
    req = urllib.request.Request(
        BLS_URL,
        data=payload,
        headers={'Content-Type': 'application/json', 'User-Agent': 'FSR-Research/1.0'}
    )
    print(f'  Fetching {label or series_id}...')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        series = data['Results']['series'][0]['data']
        # BLS returns newest-first — reverse to chronological
        series = list(reversed(series))
        pairs  = [(f"{s['year']}-{s['period'].replace('M','')}", s['value']) for s in series]
        pairs  = [(d, v) for d, v in pairs if v not in ('-', 'N/A', '')]
        dates  = [d for d, _ in pairs]
        vals   = [float(v) for _, v in pairs]
        print(f'    {len(vals)} months  |  latest: {vals[-1]:,.1f}  ({dates[-1]})')
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

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart(ur_dates, ur_vals, np_dates, np_vals):
    s_ur = calculate_predictability(ur_vals,  k=K) if len(ur_vals)  >= 2 else 0
    s_np = calculate_predictability(np_vals,  k=K) if len(np_vals)  >= 2 else 0

    # Month-over-month change in payrolls (the "jobs added" number people watch)
    np_mom = [np_vals[i] - np_vals[i-1] for i in range(1, len(np_vals))]
    np_mom_dates = np_dates[1:]
    s_mom = calculate_predictability(np_mom, k=K) if len(np_mom) >= 2 else 0

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

    ax_ur  = fig.add_subplot(gs[0, 0])   # unemployment rate
    ax_mom = fig.add_subplot(gs[1, 0])   # monthly jobs added
    ax_fsr = fig.add_subplot(gs[2, 0])   # rolling FSR
    ax_sc  = fig.add_subplot(gs[:, 1])   # score card

    for ax in [ax_ur, ax_mom, ax_fsr, ax_sc]:
        style_ax(ax)

    # Convert date strings to datetime objects for aligned x-axes
    import matplotlib.dates as mdates
    def to_dt(date_strs):
        return [datetime.strptime(d + '-01', '%Y-%m-%d') for d in date_strs]

    dt_ur  = to_dt(ur_dates)
    dt_mom = to_dt(np_mom_dates)

    # Shared x limits and formatter
    x_min = min(dt_ur[0],  dt_mom[0])
    x_max = max(dt_ur[-1], dt_mom[-1])
    fmt   = mdates.DateFormatter('%b %Y')

    def apply_date_axis(ax, tight=False):
        ax.xaxis.set_major_formatter(fmt)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.set_xlim(x_min, x_max)
        plt.setp(ax.get_xticklabels(), rotation=20, ha='right',
                 fontfamily='monospace', fontsize=8, color=TEXT)

    # ── UNEMPLOYMENT RATE ─────────────────────────────────────────────────────
    glow_plot(ax_ur, dt_ur, ur_vals, CYAN, lw=2.2, label=f'Unemployment Rate  [{s_ur:.1f}]')
    ax_ur.set_ylabel('Rate (%)', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_ur.set_title('Unemployment Rate (UNRATE)', color=WHITE, fontsize=12, fontfamily='monospace', pad=8)
    apply_date_axis(ax_ur)
    leg = ax_ur.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=10, loc='upper right')
    for t in leg.get_texts(): t.set_fontfamily('monospace')

    # ── MONTHLY JOBS ADDED ────────────────────────────────────────────────────
    colors_bar = [GREEN if v >= 0 else RED for v in np_mom]
    bar_width  = 20  # days width for date-axis bars
    ax_mom.bar(dt_mom, np_mom, color=colors_bar, alpha=0.75, width=bar_width)
    ax_mom.axhline(ANALYST_EST, color=GOLD, linewidth=1.4, linestyle='--', alpha=0.85,
                   label=f'Analyst Est: +{ANALYST_EST * 1000:,} jobs (Jun 6)')
    ax_mom.set_ylabel('Jobs Added (K)', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_mom.set_title('Monthly Nonfarm Payrolls Change', color=WHITE, fontsize=12, fontfamily='monospace', pad=8)
    apply_date_axis(ax_mom)
    leg2 = ax_mom.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=10, loc='upper right')
    for t in leg2.get_texts(): t.set_fontfamily('monospace')

    # ── ROLLING FSR ───────────────────────────────────────────────────────────
    for vals, dt_dates, color, label in [
        (ur_vals, dt_ur,  CYAN, f'Unemployment FSR  {s_ur:.1f}'),
        (np_mom,  dt_mom, PINK, f'Payrolls MoM FSR  {s_mom:.1f}'),
    ]:
        if len(vals) < WINDOW + 1:
            continue
        sw     = calculate_sliding_window(vals, WINDOW, k=K)
        sw_y   = [r['score'] for r in sw]
        sw_x   = dt_dates[WINDOW - 1:]   # align window end to actual dates
        ax_fsr.fill_between(sw_x, sw_y, alpha=0.08, color=color)
        ax_fsr.plot(sw_x, sw_y, color=color, linewidth=2.0, label=label)
        ax_fsr.scatter([sw_x[-1]], [sw_y[-1]], color=color, s=55, zorder=5, edgecolors=BG, linewidths=1.5)
        ax_fsr.text(sw_x[-1], sw_y[-1] + 3, f'{sw_y[-1]:.0f}', color=color, fontsize=9,
                    va='bottom', ha='right', fontfamily='monospace')

    ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.axhline(45, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.text(dt_ur[0], 71.5, 'CONSISTENT', color=GREEN, fontsize=8, alpha=0.6, fontfamily='monospace')
    ax_fsr.text(dt_ur[0], 46.5, 'MODERATE',   color=GOLD,  fontsize=8, alpha=0.6, fontfamily='monospace')
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_fsr.set_xlabel('')
    ax_fsr.set_title(f'FSR Predictability Score — {WINDOW}-Month Rolling Window',
                     color=WHITE, fontsize=12, fontfamily='monospace', pad=8)
    apply_date_axis(ax_fsr)
    leg3 = ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=10, loc='upper right')
    for t in leg3.get_texts(): t.set_fontfamily('monospace')

    # ── SCORE CARD ────────────────────────────────────────────────────────────
    ax_sc.set_xlim(0, 1); ax_sc.set_ylim(0, 1)
    ax_sc.set_xticks([]); ax_sc.set_yticks([])

    ax_sc.text(0.5, 0.975, 'FSR VERDICT', ha='center', va='top',
               fontsize=11, color=DIM, fontfamily='monospace', fontweight='bold')
    ax_sc.text(0.5, 0.935, 'Jobs Report Preview', ha='center', va='top',
               fontsize=9, color=DIM, fontfamily='monospace')

    badges = [
        ('Unemployment',  s_ur,  CYAN),
        ('Payrolls MoM',  s_mom, PINK),
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

    # Analyst est callout
    ax_sc.text(0.5, 0.175, 'ANALYST ESTIMATE', ha='center', fontsize=8,
               color=DIM, fontfamily='monospace')
    ax_sc.text(0.5, 0.120, f'+{ANALYST_EST * 1000:,}', ha='center', fontsize=22,
               fontweight='bold', color=GOLD, fontfamily='monospace')
    ax_sc.text(0.5, 0.070, 'Nonfarm Payrolls', ha='center', fontsize=8,
               color=DIM, fontfamily='monospace')
    ax_sc.text(0.5, 0.030, 'Jun 6  8:30am ET', ha='center', fontsize=8,
               color=GOLD, fontfamily='monospace', alpha=0.8)

    # ── HEADER ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             'JOBS REPORT FRIDAY JUN 6 — WHAT DOES THE DATA SAY GOING IN?',
             ha='center', fontsize=18, fontweight='bold', color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.930,
             'Unemployment Rate  ·  Nonfarm Payrolls  ·  FSR Predictability Score™  ·  Data: BLS.gov',
             ha='center', fontsize=10, color=DIM, fontfamily='monospace')

    ts_str = datetime.now().strftime('%Y-%m-%d')
    fig.text(0.97, 0.012,
             f'Data: bls.gov  ·  {ts_str}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    plt.savefig(OUT, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f'\nSaved: {OUT}')
    plt.show()

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Jobs Report FSR — YouTube Chart')
    print('=' * 40)

    ur_dates, ur_vals = fetch_bls(SERIES_UNRATE, 'Unemployment Rate')
    np_dates, np_vals = fetch_bls(SERIES_PAYEMS, 'Nonfarm Payrolls')

    if not ur_vals or not np_vals:
        print('\nERROR: Could not fetch BLS data. Check your connection.')
        exit(1)

    for label, vals in [('Unemployment Rate', ur_vals), ('Nonfarm Payrolls', np_vals)]:
        score = calculate_predictability(vals, k=K)
        print(f'  {label:<22} FSR: {score:.1f}  [{score_label(score)}]')

    print('\nBuilding chart...')
    build_chart(ur_dates, ur_vals, np_dates, np_vals)
