#!/usr/bin/env python3
"""
nhl_playoff_compare.py — 2026 NHL Playoff FSR Comparison
=========================================================
Full regular season + playoff game logs per star player.
Runs FSR on combined dataset, draws a divider where playoffs begin.

Usage:  python nhl_playoff_compare.py
"""

import time
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from io import StringIO
from bs4 import BeautifulSoup, Comment
from datetime import datetime
import unidecode

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── TEAMS & STARS ─────────────────────────────────────────────────────────────
TEAMS = [
    {"team": "Montreal Canadiens",  "player": "Nick Suzuki",      "abbr": "MTL", "color": "#AF1E2D"},
    {"team": "Carolina Hurricanes", "player": "Sebastian Aho",     "abbr": "CAR", "color": "#CC0000"},
    {"team": "Vegas Golden Knights","player": "Jack Eichel",       "abbr": "VGK", "color": "#B4975A"},
    {"team": "Colorado Avalanche",  "player": "Nathan MacKinnon",  "abbr": "COL", "color": "#6F263D"},
]

YEAR     = 2026
K_FACTOR = 0.5  # Sports standard
WINDOW   = 10   # bigger window now that we have 90+ games

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG    = '#080810'
PANEL = '#0d0d1c'
GRID  = '#1a1a2e'
TEXT  = '#d4d4f0'
DIM   = '#5a5a8a'
WHITE = '#f0f0ff'

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; FSR-Research/1.0)'}

# ── SCRAPING ──────────────────────────────────────────────────────────────────
def player_url(name, year):
    clean = unidecode.unidecode(name.lower())
    parts = clean.split()
    last, first = parts[-1], parts[0]
    slug = last[:5] + first[:2] + "01"
    base = f"https://www.hockey-reference.com/players/{last[0]}/{slug}/gamelog/{year}"
    return base, slug

def fetch_gamelog(name, year):
    url, _ = player_url(name, year)
    print(f"  Fetching {name} @ {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR: {e}")
        return [], [], 0

    soup = BeautifulSoup(r.content, 'html.parser')

    def extract_table(table_id):
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            if f'id="{table_id}"' in comment:
                try:
                    df = pd.read_html(StringIO(str(comment)))[0]
                    if not df.empty:
                        return df
                except Exception:
                    pass
        div = soup.find('table', id=table_id)
        if div:
            try:
                df = pd.read_html(StringIO(str(div)))[0]
                if not df.empty:
                    return df
            except Exception:
                pass
        return None

    def clean(df):
        if df is None:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(-1)
        mask = pd.to_numeric(df.get('Rk', df.iloc[:, 0]), errors='coerce').notna()
        return df[mask].copy()

    def to_pts(df):
        if df is None:
            return []
        for col in ['PTS', 'P', 'Points']:
            if col in df.columns:
                return pd.to_numeric(df[col], errors='coerce').fillna(0).tolist()
        return []

    rs_vals = to_pts(clean(extract_table('gamelog')))
    po_raw  = clean(extract_table('gamelog_playoffs'))
    if po_raw is None:
        po_raw = clean(extract_table('playoffs_gamelog'))
    po_vals = to_pts(po_raw)

    rs_count = len(rs_vals)
    all_vals = rs_vals + po_vals
    print(f"  RS: {rs_count} games | PO: {len(po_vals)} games | Total: {len(all_vals)}")
    time.sleep(1.2)
    return list(range(1, len(all_vals) + 1)), all_vals, rs_count

# ── HELPERS ───────────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 75: return '#00e676'
    if s >= 55: return '#ffca28'
    return '#ff3d3d'

def score_label(s):
    if s >= 90: return 'ELITE'
    if s >= 75: return 'CONSISTENT'
    if s >= 55: return 'MODERATE'
    if s >= 35: return 'STREAKY'
    return 'VOLATILE'

# ── CHART ─────────────────────────────────────────────────────────────────────
def build_chart(results):
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)

    gs = gridspec.GridSpec(
        2, 5,
        width_ratios=[1, 1, 1, 1, 0.75],
        height_ratios=[1.35, 1],
        hspace=0.44, wspace=0.28,
        left=0.04, right=0.97,
        top=0.87, bottom=0.08,
    )

    valid = [r for r in results if r['vals']]

    # ── TOP ROW: points per game bars ─────────────────────────────────────────
    for col, r in enumerate(valid):
        ax = fig.add_subplot(gs[0, col])
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.tick_params(colors=TEXT, labelsize=7.5)

        xs   = r['games']
        ys   = r['vals']
        rsc  = r['rs_count']
        avg  = np.mean(ys)
        rs_avg = np.mean(ys[:rsc]) if rsc else avg
        po_avg = np.mean(ys[rsc:]) if rsc < len(ys) else avg

        # RS bars dimmer, PO bars bright
        rs_colors = [r['color'] + '88'] * rsc
        po_colors = [r['color']] * (len(ys) - rsc)
        all_colors = rs_colors + po_colors

        ax.bar(xs, ys, color=all_colors, width=0.75, zorder=3)
        ax.axhline(avg, color='#888', linewidth=0.9, linestyle='--', alpha=0.5,
                   label=f'Season avg: {avg:.2f}')

        # Playoff divider
        if rsc and rsc < len(xs):
            ax.axvline(rsc + 0.5, color=WHITE, linewidth=1.2,
                       linestyle=':', alpha=0.6)
            ax.text(rsc + 0.8, max(ys) + 0.3, 'PLAYOFFS',
                    fontsize=6.5, color=WHITE, alpha=0.6,
                    fontfamily='monospace')

        ax.set_xlim(0.3, max(xs) + 0.7)
        ax.set_ylim(0, max(ys) + 1.8)

        # Only show every ~15th x tick to avoid clutter
        tick_step = max(1, len(xs) // 6)
        ax.set_xticks(xs[::tick_step])
        ax.set_xticklabels([str(x) for x in xs[::tick_step]], fontsize=7)

        ax.set_title(f"{r['abbr']}  —  {r['player'].split()[-1]}",
                     color=r['color'], fontsize=11.5,
                     fontfamily='monospace', fontweight='bold', pad=8)
        ax.set_ylabel('Points', color=TEXT, fontsize=9)
        ax.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.7)
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                  fontsize=7.5, loc='upper left')

        # RS/PO avg labels
        if rsc and rsc < len(ys):
            ax.text(rsc * 0.5, max(ys) + 0.4,
                    f'RS: {rs_avg:.2f}', fontsize=7, color=r['color'] + 'aa',
                    ha='center', fontfamily='monospace')
            ax.text(rsc + (len(ys) - rsc) * 0.5, max(ys) + 0.4,
                    f'PO: {po_avg:.2f}', fontsize=7, color=r['color'],
                    ha='center', fontfamily='monospace')

    # ── BOTTOM: FSR rolling window ─────────────────────────────────────────────
    ax_fsr = fig.add_subplot(gs[1, :4])
    ax_fsr.set_facecolor(PANEL)
    for sp in ax_fsr.spines.values():
        sp.set_edgecolor(GRID)
    ax_fsr.tick_params(colors=TEXT, labelsize=9)

    max_games = max(len(r['games']) for r in valid) if valid else 1

    for r in valid:
        if len(r['vals']) < WINDOW + 1:
            ax_fsr.axhline(r['score'], color=r['color'], linewidth=1.5,
                           linestyle='--', alpha=0.6,
                           label=f"{r['abbr']} ({r['score']:.1f})")
            continue
        sw   = calculate_sliding_window(r['vals'], WINDOW, k=K_FACTOR)
        sw_y = [res['score'] for res in sw]
        sw_x = list(range(WINDOW, len(r['vals']) + 1))

        ax_fsr.plot(sw_x, sw_y, color=r['color'], alpha=0.10, linewidth=7,  zorder=2)
        ax_fsr.plot(sw_x, sw_y, color=r['color'], alpha=0.28, linewidth=3.5,zorder=3)
        ax_fsr.plot(sw_x, sw_y, color=r['color'], linewidth=1.8,            zorder=4,
                    label=f"{r['abbr']}  {r['score']:.1f}")
        ax_fsr.scatter([sw_x[-1]], [sw_y[-1]], color=r['color'], s=55,
                       zorder=5, edgecolors=BG, linewidths=1.5)

        # playoff divider on FSR chart too
        rsc = r['rs_count']
        if rsc and rsc < len(r['vals']):
            ax_fsr.axvline(rsc + 0.5, color=WHITE, linewidth=0.8,
                           linestyle=':', alpha=0.25)

    ax_fsr.axhline(75, color='#00e676', linewidth=0.8, linestyle=':', alpha=0.45)
    ax_fsr.axhline(55, color='#ffca28', linewidth=0.8, linestyle=':', alpha=0.45)
    ax_fsr.text(1, 76.5, 'CONSISTENT', color='#00e676', fontsize=7.5,
                alpha=0.5, fontfamily='monospace')
    ax_fsr.text(1, 56.5, 'STREAKY', color='#ffca28', fontsize=7.5,
                alpha=0.5, fontfamily='monospace')

    ax_fsr.set_xlim(0, max_games + 1)
    ax_fsr.set_ylim(0, 105)
    ax_fsr.set_xlabel('Game (regular season + playoffs)', color=DIM, fontsize=9)
    ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10)
    ax_fsr.set_title(f'FSR Predictability Score — {WINDOW}-Game Rolling Window  '
                     f'(dim bars = regular season  ·  bright bars = playoffs)',
                     color=WHITE, fontsize=11.5, fontfamily='monospace', pad=8)
    ax_fsr.grid(color=GRID, linewidth=0.5, alpha=0.7)
    ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                  fontsize=10.5, loc='lower right', ncol=4,
                  handlelength=2.2, handletextpad=0.6)

    # ── RIGHT: score badges ────────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[:, 4])
    ax_b.set_facecolor(PANEL)
    for sp in ax_b.spines.values():
        sp.set_edgecolor(GRID)
    ax_b.set_xlim(0, 1)
    ax_b.set_ylim(0, 1)
    ax_b.set_xticks([])
    ax_b.set_yticks([])

    ax_b.text(0.5, 0.975, 'FSR SCORES', ha='center', va='top',
              fontsize=9.5, color=DIM, fontfamily='monospace', fontweight='bold')

    slot = 0.88 / max(len(valid), 1)
    for i, r in enumerate(valid):
        cy = 0.9 - i * slot - slot * 0.3
        sc = score_color(r['score'])
        ax_b.add_patch(plt.Circle((0.5, cy), 0.16, fill=False,
                                   edgecolor=sc, linewidth=3, alpha=0.9))
        ax_b.text(0.5, cy + 0.02, f"{r['score']:.1f}",
                  ha='center', va='center', fontsize=19, fontweight='bold',
                  color=sc, fontfamily='monospace')
        ax_b.text(0.5, cy - 0.085, r['abbr'],
                  ha='center', fontsize=10, fontweight='bold',
                  color=r['color'], fontfamily='monospace')
        ax_b.text(0.5, cy - 0.138, score_label(r['score']),
                  ha='center', fontsize=7.5, color=sc, fontfamily='monospace')
        # games played
        total = len(r['vals'])
        po    = total - r['rs_count']
        ax_b.text(0.5, cy - 0.185, f"{r['rs_count']} RS + {po} PO",
                  ha='center', fontsize=7, color=DIM, fontfamily='monospace')

    # ── TITLES ─────────────────────────────────────────────────────────────────
    fig.text(0.5, 0.962,
             '2026 NHL PLAYOFFS  —  CONFERENCE FINALS  FSR COMPARISON',
             ha='center', fontsize=20, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.930,
             'Full season consistency  ·  Regular season + playoffs  ·  FSR Predictability Score',
             ha='center', fontsize=10.5, color=DIM, fontfamily='monospace')

    ts = datetime.now().strftime('%Y-%m-%d  %H:%M')
    fig.text(0.97, 0.012,
             f'Data: hockey-reference.com  ·  {ts}  ·  predictability-api.com',
             ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

    out = 'nhl_playoff_compare.png'
    plt.savefig(out, dpi=100, facecolor=BG, bbox_inches='tight')
    print(f"\nSaved: {out}")
    plt.show()

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("2026 NHL Playoff FSR Comparison")
    print("=" * 42)

    results = []
    for t in TEAMS:
        print(f"\n[{t['abbr']}] {t['player']}")
        games, vals, rs_count = fetch_gamelog(t['player'], YEAR)
        score = calculate_predictability(vals, k=K_FACTOR) if vals else 0.0
        results.append({**t, "games": games, "vals": vals,
                         "rs_count": rs_count, "score": score})
        print(f"  FSR Score: {score:.2f}  [{score_label(score)}]")

    print("\nBuilding chart...")
    build_chart(results)
