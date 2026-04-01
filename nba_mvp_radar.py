"""
NBA MVP Radar Chart — Predictability Score™ Edition
Compares SGA, Jokic, Wembanyama, and Luka Doncic across 6 consistency pillars.

Run: python nba_mvp_radar.py
Output: static/images/nba_charts/mvp_radar_2026.png
"""

import math
import os
import time
import warnings
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from unidecode import unidecode

from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
from fsr import calculate_predictability

warnings.filterwarnings('ignore')

# ── Theme ─────────────────────────────────────────────────────────────────────
BG    = '#0f1117'
PANEL = '#171b24'
GRID  = '#2b3442'
TEXT  = '#f5f7fa'
SUB   = '#aab6c4'

# Vivid, distinct colors — all readable on dark background
PLAYER_COLORS = {
    'Shai Gilgeous-Alexander': '#39c2ff',   # OKC electric cyan
    'Nikola Jokic':            '#ffd166',   # Denver gold
    'Victor Wembanyama':       '#00ff88',   # neon green
    'Luka Doncic':             '#ff6b9d',   # Lakers hot pink/rose
}

HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

PILLARS = [
    ('PTS', 'Scoring\nConsistency',    False),
    ('AST', 'Playmaking\nConsistency', False),
    ('REB', 'Rebounding\nConsistency', False),
    ('STL', 'Steal\nConsistency',      False),
    ('BLK', 'Block\nConsistency',      False),
    ('TOV', 'Ball Control\n(low TOV)', True),
]

SEASON = '2025-26'
K      = 0.5

CANDIDATES = [
    'Shai Gilgeous-Alexander',
    'Nikola Jokic',
    'Victor Wembanyama',
    'Luka Doncic',
]


def fetch_gamelog(player_name, retries=3):
    nba_players = players.get_players()
    matches = [p for p in nba_players
               if player_name.lower() in unidecode(p['full_name']).lower()
               or player_name.lower() in p['full_name'].lower()]
    if not matches:
        raise ValueError(f"Player not found: {player_name}")
    pid       = matches[0]['id']
    full_name = matches[0]['full_name']
    display_name = unidecode(full_name)
    print(f"  [{display_name}] Fetching {SEASON}...")
    for attempt in range(retries):
        try:
            log = playergamelog.PlayerGameLog(
                player_id=pid, season=SEASON, timeout=60, headers=HEADERS,
            ).get_data_frames()[0]
            print(f"  [{display_name}] {len(log)} games loaded.")
            return full_name, log
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep((attempt + 1) * 5)
            else:
                raise


def compute_scores(log):
    scores = {}
    for col, label, invert in PILLARS:
        if col not in log.columns:
            scores[label] = 50.0
            continue
        series = log[col].dropna().tolist()
        series.reverse()
        if len(series) < 5:
            scores[label] = 50.0
            continue
        s = calculate_predictability(series, k=K)
        scores[label] = round(100 - s if invert else s, 1)
    return scores


def build_radar(player_scores: dict, save_path: str):
    labels = [p[1] for p in PILLARS]
    N      = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig = plt.figure(figsize=(12, 10.5), facecolor=BG)
    ax  = fig.add_subplot(111, polar=True, facecolor=PANEL)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], color=SUB, fontsize=8.5)
    ax.yaxis.grid(color=GRID, linewidth=0.8, linestyle='--', alpha=0.7)
    ax.xaxis.grid(color=GRID, linewidth=0.8, linestyle='-',  alpha=0.4)
    ax.spines['polar'].set_color(GRID)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color=TEXT, fontsize=11, fontweight='bold')

    # Elite / avg reference rings
    for ring, color, lw, alpha, lbl in [
        (60, '#ffaa00', 1.2, 0.30, 'Volatile (60)'),
        (80, '#39c2ff', 1.5, 0.40, 'Elite (80)'),
    ]:
        ring_vals = [ring] * N + [ring]
        ax.plot(angles, ring_vals, color=color, linewidth=lw,
                alpha=alpha, linestyle='--', zorder=2)

    legend_patches = []
    for pname, pillar_dict in player_scores.items():
        color  = PLAYER_COLORS.get(pname) or \
                 PLAYER_COLORS.get(unidecode(pname)) or \
                 next((v for k, v in PLAYER_COLORS.items()
                       if unidecode(k).lower() == unidecode(pname).lower()), '#ffffff')
        values = [pillar_dict.get(lbl, 50) for lbl in labels] + \
                 [pillar_dict.get(labels[0], 50)]

        ax.plot(angles, values, color=color, linewidth=3.0,
                linestyle='solid', zorder=5, alpha=0.95)
        ax.fill(angles, values, color=color, alpha=0.10, zorder=4)
        ax.scatter(angles[:-1], values[:-1], color=color,
                   s=55, zorder=6, edgecolors='#0f1117', linewidths=0.8)

        short = pname.split()[-1]
        legend_patches.append(mpatches.Patch(facecolor=color, label=short,
                                              edgecolor='#0f1117', linewidth=0.5))

    ax.legend(
        handles=legend_patches,
        loc='upper right',
        bbox_to_anchor=(1.38, 1.18),
        frameon=True, framealpha=0.35,
        facecolor=PANEL, edgecolor=GRID,
        labelcolor=TEXT, fontsize=12,
        title='Player', title_fontsize=10,
    )

    fig.text(0.5, 0.97, 'MVP CONSISTENCY RADAR  |  2025-26 NBA Season',
             ha='center', va='top', color=TEXT, fontsize=15, fontweight='bold')
    fig.text(0.5, 0.935, 'Predictability Score™  ·  k=0.5  ·  Full Season Game Logs',
             ha='center', va='top', color=SUB, fontsize=10)
    fig.text(0.5, 0.022,
             'Ball Control axis is INVERTED — higher score = fewer erratic turnover nights.',
             ha='center', va='bottom', color=SUB, fontsize=8.5, style='italic')

    plt.tight_layout(rect=[0, 0.04, 1, 0.93])
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f"\n  Saved -> {save_path}")


if __name__ == '__main__':
    print('=' * 55)
    print('  NBA MVP Radar  |  Predictability Score  |  2025-26')
    print('=' * 55)

    player_scores = {}
    for candidate in CANDIDATES:
        try:
            full_name, log = fetch_gamelog(candidate)
            player_scores[full_name] = compute_scores(log)
            time.sleep(2)
        except Exception as e:
            print(f"  ERROR for {candidate}: {e}")

    if player_scores:
        out = os.path.join('static', 'images', 'nba_charts', 'mvp_radar_2026.png')
        build_radar(player_scores, out)

        labels = [p[1].replace('\n', ' ') for p in PILLARS]
        score_keys = [p[1] for p in PILLARS]   # keys stored with \n
        print(f"\n{'Player':<30}", end='')
        for lbl in labels:
            print(f"{lbl:<24}", end='')
        print()
        print('-' * (30 + 24 * len(labels)))
        for pname, sd in player_scores.items():
            print(f"{unidecode(pname):<30}", end='')
            for key, lbl in zip(score_keys, labels):
                print(f"{sd.get(key, sd.get(lbl, 50.0)):<24.1f}", end='')
            print()
    else:
        print("No data fetched.")
