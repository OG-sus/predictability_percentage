"""
bitcoin_gen.py — Bitcoin On-Chain Transaction Volume FSR
=========================================================
Pulls daily transaction count + transfer volume from blockchain.com (free, no key).
Runs FSR on volume signals — NOT price.
YouTube-ready 1920x1080 dark 2-panel chart.

Usage:  python bitcoin_gen.py
"""

import math
import json
import urllib.request
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
from datetime import datetime, timedelta

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── CONFIG ────────────────────────────────────────────────────────────────────
TIMESPAN = '1year'
WINDOW   = 30     # 30-day rolling FSR
K        = 1.0
OUT      = 'bitcoin_gen.png'

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

C_TXN  = '#29b6f6'   # blue   — daily transactions
C_VOL  = '#f06292'   # pink   — transfer volume
C_UTXO = '#ab47bc'   # purple — UTXOs (on-chain activity)

# ── FETCH ─────────────────────────────────────────────────────────────────────
BASE = 'https://api.blockchain.info/charts'

def fetch_chart(chart, timespan=TIMESPAN, label=''):
    url = f'{BASE}/{chart}?timespan={timespan}&sampled=true&format=json&cors=true'
    print(f'  Fetching {label or chart}...')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FSR-Research/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        pts  = data.get('values', [])
        vals = [p['y'] for p in pts]
        ts   = [datetime.fromtimestamp(p['x']) for p in pts]
        print(f'    {len(vals)} data points  |  last: {vals[-1]:,.0f}')
        return ts, vals
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

def human_num(v):
    if v >= 1_000_000_000: return f'{v/1_000_000_000:.1f}B'
    if v >= 1_000_000:     return f'{v/1_000_000:.1f}M'
    if v >= 1_000:         return f'{v/1_000:.1f}K'
    return f'{v:.0f}'

def style_ax(ax):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    ax.tick_params(colors=TEXT, labelsize=10)
    ax.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.7)
    ax.grid(axis='x', color=GRID, linewidth=0.3, alpha=0.35)

def glow_plot(ax, xs, ys, color, lw=2.2, label='', zorder=5):
    ax.fill_between(xs, ys, alpha=0.07, color=color, zorder=zorder - 2)
    ax.plot(xs, ys, color=color, alpha=0.12, linewidth=lw * 5,  zorder=zorder - 1,
            solid_capstyle='round')
    ax.plot(xs, ys, color=color, alpha=0.30, linewidth=lw * 2,  zorder=zorder,
            solid_capstyle='round')
    ax.plot(xs, ys, color=color, linewidth=lw,                  zorder=zorder + 1,
            label=label, solid_capstyle='round')
    ax.scatter([xs[-1]], [ys[-1]], color=color, s=55,
               zorder=zorder + 2, edgecolors=BG, linewidths=1.5)

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart(txn_ts, txn_vals, vol_ts, vol_vals, utxo_ts, utxo_vals):
    s_txn  = calculate_predictability(txn_vals,  k=K) if len(txn_vals)  >= 2 else 0
    s_vol  = calculate_predictability(vol_vals,  k=K) if len(vol_vals)  >= 2 else 0
    s_utxo = calculate_predictability(utxo_vals, k=K) if len(utxo_vals) >= 2 else 0

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

    ax_lines = fig.add_subplot(gs[0, 0])   # raw on-chain signals
    ax_fsr   = fig.add_subplot(gs[1, 0])   # rolling FSR
    ax_score = fig.add_subplot(gs[:, 1])   # score card

    for ax in [ax_lines, ax_fsr, ax_score]:
        style_ax(ax)

    # Align all datasets to the shortest (txn/vol are ~362, utxo is 1516 — trim to match)
    n = min(len(txn_vals) if txn_vals else 9999,
            len(vol_vals)  if vol_vals  else 9999,
            len(utxo_vals) if utxo_vals else 9999)
    if txn_vals:  txn_vals  = txn_vals[-n:];  txn_ts  = txn_ts[-n:]
    if vol_vals:  vol_vals  = vol_vals[-n:];  vol_ts  = vol_ts[-n:]
    if utxo_vals: utxo_vals = utxo_vals[-n:]
    xs = list(range(n))

    # ── RAW SIGNAL LINES ──────────────────────────────────────────────────────
    # Normalize each to 100 at start, cap spikes at 98th percentile for display
    def norm(vals, cap_pct=98):
        base = vals[0] if vals[0] != 0 else 1
        normed = [v / base * 100 for v in vals]
        cap = float(np.percentile(normed, cap_pct))
        return [min(v, cap) for v in normed]

    datasets = []
    if txn_vals:
        datasets.append((txn_vals,  txn_ts,  C_TXN,  'Daily Transactions',  s_txn))
    if vol_vals:
        datasets.append((vol_vals,  vol_ts,  C_VOL,  'Transfer Volume (BTC)', s_vol))
    if utxo_vals:
        datasets.append((utxo_vals, utxo_ts, C_UTXO, 'UTXOs Created',        s_utxo))

    for vals, ts, color, label, score in datasets:
        ys = norm(vals)
        lx = list(range(len(ys)))
        glow_plot(ax_lines, lx, ys, color, lw=2.0,
                  label=f'{label}  [{score:.1f}]')
        ax_lines.text(len(ys) - 1 + 0.5, ys[-1],
                      f'{ys[-1]:.0f}', color=color, fontsize=8.5,
                      va='center', fontfamily='monospace')

    ax_lines.axhline(100, color=DIM, linewidth=0.8, linestyle='--', alpha=0.4)
    ax_lines.text(0.5, 101.5, 'baseline (start=100)', color=DIM, fontsize=8,
                  fontfamily='monospace', alpha=0.6)

    # Date labels on x axis — show ~6 evenly spaced
    if txn_ts:
        tick_step = max(n // 6, 1)
        tick_idx  = list(range(0, n, tick_step))
        ax_lines.set_xticks(tick_idx)
        ax_lines.set_xticklabels(
            [txn_ts[i].strftime('%b %Y') for i in tick_idx],
            fontfamily='monospace', fontsize=9
        )

    ax_lines.set_xlim(-2, n + 8)
    ax_lines.set_ylabel('Relative (start = 100)', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_lines.set_title('Bitcoin On-Chain Activity — 1 Year  (NOT Price)',
                       color=WHITE, fontsize=13, fontfamily='monospace', pad=10)

    leg = ax_lines.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                          fontsize=10, loc='upper left', handlelength=1.6)
    for t in leg.get_texts():
        t.set_fontfamily('monospace')

    # ── ROLLING FSR ───────────────────────────────────────────────────────────
    fsr_entries = [
        (txn_vals,  C_TXN,  f'Daily Txns    {s_txn:.1f}', s_txn),
        (vol_vals,  C_VOL,  f'Volume (BTC)  {s_vol:.1f}', s_vol),
        (utxo_vals, C_UTXO, f'UTXOs         {s_utxo:.1f}', s_utxo),
    ]
    for vals, color, label, fsr_score in fsr_entries if datasets else []:
        if len(vals) < WINDOW + 1:
            continue
        sw   = calculate_sliding_window(vals, WINDOW, k=K)
        sw_y = [r['score'] for r in sw]
        sw_x = list(range(WINDOW - 1, len(vals)))

        ax_fsr.fill_between(sw_x, sw_y, alpha=0.08, color=color)
        ax_fsr.plot(sw_x, sw_y, color=color, linewidth=2.0, label=label)
        ax_fsr.scatter([sw_x[-1]], [sw_y[-1]], color=color, s=55,
                       zorder=5, edgecolors=BG, linewidths=1.5)
        ax_fsr.text(sw_x[-1] + 0.5, sw_y[-1], f'{sw_y[-1]:.0f}',
                    color=color, fontsize=9, va='center', fontfamily='monospace')
        _ = fsr_score  # suppress unused warning

    ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.axhline(45, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.5)
    ax_fsr.text(0.5, 71.5, 'CONSISTENT', color=GREEN, fontsize=8, alpha=0.6,
                fontfamily='monospace')
    ax_fsr.text(0.5, 46.5, 'MODERATE',   color=GOLD,  fontsize=8, alpha=0.6,
                fontfamily='monospace')

    if txn_ts:
        ax_fsr.set_xticks(tick_idx)
        ax_fsr.set_xticklabels(
            [txn_ts[i].strftime('%b %Y') for i in tick_idx],
            fontfamily='monospace', fontsize=9
        )
    ax_fsr.set_xlim(-2, n + 8)
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10, fontfamily='monospace')
    ax_fsr.set_xlabel(f'{WINDOW}-Day Rolling FSR Window  ·  k={K}  ·  On-chain data',
                      color=DIM, fontsize=9, fontfamily='monospace')
    ax_fsr.set_title(f'FSR Predictability Score — {WINDOW}-Day Rolling Window',
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
    ax_score.text(0.5, 0.935, 'On-Chain Signals', ha='center', va='top',
                  fontsize=9, color=DIM, fontfamily='monospace')

    badges = [
        ('Daily Txns',   s_txn,  C_TXN),
        ('Transfer Vol', s_vol,  C_VOL),
        ('UTXOs',        s_utxo, C_UTXO),
    ]
    slot_h = 0.255
    tops   = [0.88, 0.88 - slot_h, 0.88 - slot_h * 2]

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

    # Latest value callouts
    stats = []
    if txn_vals:  stats.append(f'Txns: {human_num(txn_vals[-1])}/day')
    if vol_vals:  stats.append(f'Vol: {human_num(vol_vals[-1])} BTC')
    ax_score.text(0.5, 0.025, '  ·  '.join(stats),
                  ha='center', fontsize=7.5, color=DIM, fontfamily='monospace')

    # ── HEADER ────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             'BITCOIN ON-CHAIN ACTIVITY  —  HOW PREDICTABLE IS THE NETWORK?',
             ha='center', fontsize=19, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.930,
             'Daily Transactions  ·  Transfer Volume  ·  UTXOs  '
             '·  FSR Predictability Score™  ·  NOT Price  ·  Data: Blockchain.com',
             ha='center', fontsize=10, color=DIM, fontfamily='monospace')

    ts_str = datetime.now().strftime('%Y-%m-%d')
    fig.text(0.97, 0.012,
             f'Data: blockchain.info/charts  ·  {ts_str}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    plt.savefig(OUT, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f'Saved: {OUT}')
    plt.show()

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Bitcoin On-Chain FSR — YouTube Chart')
    print('=' * 40)

    txn_ts,  txn_vals  = fetch_chart('n-transactions',         label='Daily Transactions')
    vol_ts,  vol_vals  = fetch_chart('estimated-transaction-volume', label='Transfer Volume (BTC)')
    utxo_ts, utxo_vals = fetch_chart('utxo-count',             label='UTXOs Created')

    for label, vals, k in [
        ('Daily Transactions', txn_vals,  K),
        ('Transfer Volume',    vol_vals,  K),
        ('UTXO Count',         utxo_vals, K),
    ]:
        if vals:
            score = calculate_predictability(vals, k=k)
            print(f'  {label:<22} FSR: {score:.1f}  [{score_label(score)}]')

    print()
    print('Building chart...')
    build_chart(txn_ts, txn_vals, vol_ts, vol_vals, utxo_ts, utxo_vals)
