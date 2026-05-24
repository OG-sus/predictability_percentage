#!/usr/bin/env python3
"""
eth_yt_chart.py — Ethereum Gas Fee Predictability (YouTube Edition)
====================================================================
Pulls live ETH gas fees (last N blocks), runs FSR, outputs a single
16:9 YouTube-ready chart. No API key needed.

Usage:
    python eth_yt_chart.py            # 100 blocks
    python eth_yt_chart.py 150        # custom block count
"""

import sys
import time
import requests
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── CONFIG ────────────────────────────────────────────────────────────────────
RPC_FALLBACKS = [
    'https://rpc.ankr.com/eth',
    'https://ethereum.publicnode.com',
    'https://eth-mainnet.public.blastapi.io',
    'https://1rpc.io/eth',
    'https://eth.llamarpc.com',
    'https://cloudflare-eth.com',
]
RPC_URL     = None  # resolved at runtime
_CACHED_TIP = None  # block number from successful probe
NUM_BLOCKS  = int(sys.argv[1]) if len(sys.argv) > 1 else 100
K_FACTOR    = 2.0
WINDOW_SIZE = 15
OUT_FILE    = 'eth_gas_yt.png'

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG       = '#080812'
PANEL    = '#0d0d1f'
ETH_BLUE = '#627eea'
GRID_C   = '#1a1a30'
TEXT     = '#d4d4f0'
DIM      = '#5a5a8a'
WHITE    = '#f0f0ff'
GREEN    = '#00e676'
YELLOW   = '#ffca28'
RED      = '#ff3d3d'

SESSION = requests.Session()
SESSION.headers.update({'Content-Type': 'application/json'})

# ── RPC HELPERS ───────────────────────────────────────────────────────────────
def _rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'method': method, 'params': params or [], 'id': 1}
    r = SESSION.post(RPC_URL, json=payload, timeout=12)
    r.raise_for_status()
    data = r.json()
    if 'error' in data:
        raise ValueError(data['error'])
    return data['result']

def resolve_rpc():
    global RPC_URL, _CACHED_TIP
    for url in RPC_FALLBACKS:
        try:
            payload = {'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1}
            r = SESSION.post(url, json=payload, timeout=8)
            r.raise_for_status()
            data = r.json()
            result = data.get('result')
            if not result or 'error' in data:
                print(f"  skipping {url} (bad result)")
                continue
            _CACHED_TIP = int(result, 16)
            RPC_URL = url
            print(f"RPC: {url}  (block #{_CACHED_TIP:,})")
            return
        except Exception as e:
            print(f"  skipping {url}: {e}")
    raise ConnectionError("All RPC endpoints unavailable.")

def latest_block():
    if _CACHED_TIP:
        return _CACHED_TIP
    return int(_rpc('eth_blockNumber'), 16)

def get_block(num_hex):
    return _rpc('eth_getBlockByNumber', [num_hex, False])

# ── FETCH DATA ────────────────────────────────────────────────────────────────
def fetch_gas(num_blocks):
    resolve_rpc()
    print(f"Connecting to Ethereum mainnet...")
    tip = latest_block()
    print(f"Latest block: #{tip:,}  |  Fetching {num_blocks} blocks...")

    gwei_series, block_nums = [], []
    for i in range(num_blocks):
        bn = tip - (num_blocks - 1 - i)
        for attempt in range(3):
            try:
                blk = get_block(hex(bn))
                if blk and blk.get('baseFeePerGas'):
                    gwei = int(blk['baseFeePerGas'], 16) / 1e9
                    gwei_series.append(round(gwei, 4))
                    block_nums.append(bn)
                break
            except Exception:
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))
        time.sleep(0.08)

    print(f"Got {len(gwei_series)} data points.\n")
    return gwei_series, block_nums

# ── SCORE COLOR ───────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 75: return GREEN
    if s >= 50: return YELLOW
    return RED

def score_label(s):
    if s >= 90: return 'ELITE'
    if s >= 75: return 'STABLE'
    if s >= 60: return 'MODERATE'
    if s >= 40: return 'VOLATILE'
    return 'CHAOTIC'

def bar_color(val, mean, std):
    dev = abs(val - mean) / (std + 1e-9)
    if dev < 0.5:  return '#00c853'
    if dev < 1.0:  return '#76b900'
    if dev < 1.5:  return '#ffca28'
    if dev < 2.5:  return '#ff6d00'
    return '#ff1744'

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart(gwei, block_nums, score, sw_scores):
    arr  = np.array(gwei)
    mean = arr.mean()
    std  = arr.std()
    xs   = list(range(len(gwei)))

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)

    # ── LAYOUT: main plot + score badge column ──
    gs = fig.add_gridspec(
        2, 2,
        width_ratios=[3.2, 1],
        height_ratios=[1.65, 1],
        hspace=0.38, wspace=0.06,
        left=0.05, right=0.97,
        top=0.88, bottom=0.09,
    )
    ax_bar  = fig.add_subplot(gs[0, 0])   # gas bars
    ax_fsr  = fig.add_subplot(gs[1, 0])   # FSR sliding window
    ax_logo = fig.add_subplot(gs[:, 1])   # score badge (spans both rows)

    for ax in (ax_bar, ax_fsr, ax_logo):
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID_C)
        ax.tick_params(colors=TEXT, labelsize=9)

    # ── BAR CHART ──────────────────────────────────────────────────────────────
    colors = [bar_color(v, mean, std) for v in gwei]
    ax_bar.bar(xs, gwei, color=colors, width=0.85, alpha=0.88, zorder=3)

    # stable band: mean ± 0.5 std
    ax_bar.axhspan(mean - 0.5*std, mean + 0.5*std,
                   facecolor='#00c853', alpha=0.06, zorder=2)
    ax_bar.axhline(mean, color='#888', linewidth=1.2, linestyle='--',
                   alpha=0.7, zorder=4, label=f'Mean: {mean:.3f} Gwei')

    ax_bar.set_xlim(-1, len(xs))
    ax_bar.set_ylabel('Base Fee (Gwei)', color=TEXT, fontsize=11, labelpad=10)
    ax_bar.set_title(
        f'ETH Base Fee per Block  ·  Last {len(gwei)} blocks  (#{block_nums[0]:,} → #{block_nums[-1]:,})',
        color=WHITE, fontsize=13, fontfamily='monospace', pad=10
    )
    ax_bar.grid(axis='y', color=GRID_C, linewidth=0.6, alpha=0.9, zorder=1)
    ax_bar.set_xticks([])

    # min/max callouts
    i_max = int(np.argmax(arr))
    i_min = int(np.argmin(arr))
    for idx, label, va in [(i_max, f'{arr[i_max]:.2f}', 'bottom'),
                            (i_min, f'{arr[i_min]:.2f}', 'top')]:
        ax_bar.annotate(label, xy=(idx, gwei[idx]),
                        xytext=(idx, gwei[idx] + (std*0.6 if va=='bottom' else -std*0.6)),
                        ha='center', va=va, fontsize=8, color=WHITE,
                        fontfamily='monospace',
                        arrowprops=dict(arrowstyle='->', color=DIM, lw=0.8))

    legend = ax_bar.legend(facecolor=PANEL, edgecolor=GRID_C,
                           labelcolor=TEXT, fontsize=9, loc='upper left')

    # color legend
    for col, lbl in [('#00c853','<0.5σ  stable'), ('#ffca28','1–1.5σ  elevated'),
                     ('#ff6d00','1.5–2.5σ  spike'), ('#ff1744','>2.5σ  extreme')]:
        legend.get_patches()  # just ensure it exists
        ax_bar.bar([], [], color=col, label=lbl)
    ax_bar.legend(facecolor=PANEL, edgecolor=GRID_C, labelcolor=TEXT,
                  fontsize=8.5, loc='upper right', ncol=2,
                  handlelength=1.2, handletextpad=0.5, borderpad=0.6)

    # ── FSR SLIDING WINDOW ─────────────────────────────────────────────────────
    padded = [None] * (WINDOW_SIZE - 1) + sw_scores
    valid_x = [i for i, v in enumerate(padded) if v is not None]
    valid_y = [v for v in padded if v is not None]

    # color segments by score
    for i in range(len(valid_x) - 1):
        seg_score = valid_y[i]
        ax_fsr.plot(valid_x[i:i+2], valid_y[i:i+2],
                    color=score_color(seg_score), linewidth=2.2, solid_capstyle='round')

    ax_fsr.fill_between(valid_x, valid_y, 0, alpha=0.07,
                        color=score_color(score))

    ax_fsr.axhline(80, color=GREEN,  linewidth=0.8, linestyle=':', alpha=0.6)
    ax_fsr.axhline(50, color=YELLOW, linewidth=0.8, linestyle=':', alpha=0.6)
    ax_fsr.axhline(score, color=score_color(score), linewidth=1.1,
                   linestyle='--', alpha=0.5)

    ax_fsr.set_xlim(-1, len(xs))
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10, labelpad=10)
    ax_fsr.set_xlabel(f'Block (relative,  {WINDOW_SIZE}-block rolling window)',
                      color=DIM, fontsize=9)
    ax_fsr.set_title('Predictability Score™ — Rolling Window',
                     color=WHITE, fontsize=12, fontfamily='monospace', pad=8)
    ax_fsr.grid(color=GRID_C, linewidth=0.5, alpha=0.8)

    ax_fsr.text(len(xs)*0.01, 82, 'STABLE', color=GREEN,
                fontsize=7.5, alpha=0.6, fontfamily='monospace')
    ax_fsr.text(len(xs)*0.01, 52, 'VOLATILE', color=YELLOW,
                fontsize=7.5, alpha=0.6, fontfamily='monospace')

    # ── SCORE BADGE ────────────────────────────────────────────────────────────
    ax_logo.set_xlim(0, 1)
    ax_logo.set_ylim(0, 1)
    ax_logo.set_xticks([])
    ax_logo.set_yticks([])
    for sp in ax_logo.spines.values():
        sp.set_visible(False)

    sc  = score_color(score)
    lbl = score_label(score)

    # outer ring
    ring = plt.Circle((0.5, 0.60), 0.38, fill=False, edgecolor=sc,
                       linewidth=4, alpha=0.9)
    ax_logo.add_patch(ring)
    inner = plt.Circle((0.5, 0.60), 0.34, fill=True,
                        facecolor=BG, edgecolor='none', alpha=0.95)
    ax_logo.add_patch(inner)

    # score number
    ax_logo.text(0.5, 0.64, f'{score:.1f}',
                 ha='center', va='center', fontsize=52, fontweight='bold',
                 color=sc, fontfamily='monospace')
    ax_logo.text(0.5, 0.43, '/ 100',
                 ha='center', va='center', fontsize=16,
                 color=DIM, fontfamily='monospace')

    # label below ring
    ax_logo.text(0.5, 0.175, lbl,
                 ha='center', va='center', fontsize=18, fontweight='bold',
                 color=sc, fontfamily='monospace',
                 bbox=dict(boxstyle='round,pad=0.5', facecolor=BG,
                           edgecolor=sc, linewidth=1.5, alpha=0.9))

    ax_logo.text(0.5, 0.04, 'FSR Predictability Score™',
                 ha='center', va='bottom', fontsize=8.5,
                 color=DIM, fontfamily='monospace')

    # stats
    ax_logo.text(0.5, 0.93, f'avg  {mean:.3f} Gwei',
                 ha='center', fontsize=9.5, color=TEXT, fontfamily='monospace')
    ax_logo.text(0.5, 0.87, f'std   {std:.3f}',
                 ha='center', fontsize=9.5, color=TEXT, fontfamily='monospace')
    ax_logo.text(0.5, 0.81, f'max  {arr.max():.3f}',
                 ha='center', fontsize=9.5, color=RED, fontfamily='monospace')
    ax_logo.text(0.5, 0.75, f'min   {arr.min():.3f}',
                 ha='center', fontsize=9.5, color=GREEN, fontfamily='monospace')

    # ── TITLES ─────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.955,
             'ETHEREUM GAS FEES  —  PREDICTABILITY ANALYSIS',
             ha='center', va='top', fontsize=22, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.926,
             f'How stable is ETH gas right now?  Powered by FSR Predictability Score™',
             ha='center', va='top', fontsize=11.5, color=DIM, fontfamily='monospace')

    # timestamp
    ts = datetime.utcnow().strftime('%Y-%m-%d  %H:%M UTC')
    fig.text(0.97, 0.012, f'Live data · {ts} · predictabilitycalculator.com',
             ha='right', va='bottom', fontsize=8, color='#2a2a45',
             fontfamily='monospace')

    # ETH logo text
    fig.text(0.03, 0.012, 'ethereum mainnet  ·  eth_basefee  ·  no api key',
             ha='left', va='bottom', fontsize=8, color='#2a2a45',
             fontfamily='monospace')

    plt.savefig(OUT_FILE, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f"Saved: {OUT_FILE}")
    plt.show()


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    gwei, block_nums = fetch_gas(NUM_BLOCKS)
    if len(gwei) < WINDOW_SIZE + 2:
        print("Not enough data. Try more blocks.")
        sys.exit(1)

    score = calculate_predictability(gwei, k=K_FACTOR)
    sw    = calculate_sliding_window(gwei, WINDOW_SIZE, k=K_FACTOR)
    sw_scores = [r['score'] for r in sw]

    print(f"FSR Score: {score:.2f}  [{score_label(score)}]")
    print(f"Mean gas:  {np.mean(gwei):.4f} Gwei")
    print(f"Std dev:   {np.std(gwei):.4f}\n")

    build_chart(gwei, block_nums, score, sw_scores)
