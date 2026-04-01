"""
NBA MVP FSR Matchup Charts — 2025-26 Season
Produces two charts in the same style as MLB pitcher matchup charts:
  - Chart 1: Shai Gilgeous-Alexander  vs  Nikola Jokic   (SGA vs The Joker)
  - Chart 2: Victor Wembanyama        vs  Luka Doncic     (Wemby vs Luka)

Each chart = 2x2 grid:
  Top row    = raw PTS-per-game series + golden avg line + FSR badge
  Bottom row = sliding 10-game FSR Predictability Score™ window

Run: python nba_mvp_fsr.py
Output: static/images/nba_charts/mvp_sga_jokic_2026.png
        static/images/nba_charts/mvp_wemby_luka_2026.png
"""

import os
import time
import warnings
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from unidecode import unidecode

from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

warnings.filterwarnings('ignore')

# ── Visual theme (matches mlb_326_2026_graphs.py exactly) ────────────────────
BG      = '#0f1117'
PANEL   = '#171b24'
GRID    = '#2b3442'
TEXT    = '#f5f7fa'
SUB     = '#aab6c4'
ACCENT  = '#39c2ff'
GOLD    = '#ffd166'
ELITE   = '#00ff88'
VOLATILE= '#ffaa00'

SPORTS_K    = 0.5
WINDOW_SIZE = 10    # 10-game rolling window for NBA (vs 5-start for MLB)
SEASON      = '2025-26'
NUM_GAMES   = 75    # pull up to 75 games (full season minus rest/injury)

OUTPUT_DIR = os.path.join('static', 'images', 'nba_charts')

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

# ── Matchup definitions ───────────────────────────────────────────────────────
MATCHUPS = [
    {
        "player1": {"name": "Shai Gilgeous-Alexander", "color": "#007ac1", "team": "OKC"},
        "player2": {"name": "Nikola Jokic",            "color": "#fdb927", "team": "DEN"},
        "stat": "PTS",
        "title": "Shai Gilgeous-Alexander  vs  Nikola Jokić  —  Scoring Consistency",
        "subtitle_label": "Scoring Predictability",
        "filename": "mvp_sga_jokic_2026.png",
    },
    {
        "player1": {"name": "Victor Wembanyama", "color": "#c4ced4", "team": "SAS"},
        "player2": {"name": "Luka Doncic",       "color": "#552583", "team": "LAL"},
        "stat": "PTS",
        "title": "Victor Wembanyama  vs  Luka Dončić  —  Scoring Consistency",
        "subtitle_label": "Scoring Predictability",
        "filename": "mvp_wemby_luka_2026.png",
    },
]


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_pts_series(player_name: str, retries: int = 3):
    """Returns (dates_list, pts_list) in chronological order."""
    nba_players = players.get_players()
    matches = [p for p in nba_players
               if player_name.lower() in unidecode(p['full_name']).lower()
               or player_name.lower() in p['full_name'].lower()]
    if not matches:
        raise ValueError(f"Player not found: {player_name}")

    pid       = matches[0]['id']
    full_name = matches[0]['full_name']
    print(f"  [{full_name}] Fetching {SEASON} game log...")

    for attempt in range(retries):
        try:
            log = playergamelog.PlayerGameLog(
                player_id=pid,
                season=SEASON,
                timeout=60,
                headers=HEADERS,
            ).get_data_frames()[0]
            break
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep((attempt + 1) * 5)
            else:
                raise

    # log is newest-first; reverse to chronological
    log = log.iloc[::-1].reset_index(drop=True)
    log = log.tail(NUM_GAMES)

    # Format date labels: "APR 01, 2026" → "04-01"
    def _fmt(d):
        try:
            from datetime import datetime
            return datetime.strptime(d, "%b %d, %Y").strftime("%m-%d")
        except Exception:
            return str(d)[:5]

    dates = [_fmt(d) for d in log['GAME_DATE'].tolist()]
    pts   = log['PTS'].astype(int).tolist()
    print(f"  [{full_name}] {len(pts)} games  •  avg {sum(pts)/len(pts):.1f} PTS")
    return full_name, dates, pts


# ── Axis helpers (mirrors mlb_326_2026_graphs.py) ────────────────────────────

def _style_ax(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=TEXT, which='both')
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.grid(color=GRID, linestyle='--', linewidth=0.6, alpha=0.5)


def _fsr_badge(ax, score: float, color: str):
    """Draw the FSR score badge in the top-right corner."""
    badge_color = ELITE if score >= 80 else (VOLATILE if score >= 60 else '#ff4d4d')
    ax.text(0.98, 0.97,
            f"FSR  {score:.1f}",
            transform=ax.transAxes,
            ha='right', va='top',
            fontsize=14, fontweight='bold', color='#0f1117',
            bbox={"boxstyle": "round,pad=0.4",
                  "facecolor": badge_color,
                  "edgecolor": "none",
                  "alpha": 0.95})


# ── Single player panel (top=series, bottom=FSR) ─────────────────────────────

def _plot_panel(ax_top, ax_bot, full_name, dates, pts, color, stat_label="Points per game"):
    avg     = sum(pts) / len(pts)
    overall = calculate_predictability(pts, k=SPORTS_K)
    win     = min(WINDOW_SIZE, len(pts))
    windows = calculate_sliding_window(pts, window_size=win, k=SPORTS_K)
    scores  = [None] * (win - 1) + [r['score'] for r in windows]

    # ── Top: raw PTS series ───────────────────────────────────────────────────
    _style_ax(ax_top)
    ax_top.plot(dates, pts, marker='o', markersize=4, linewidth=2.4,
                color=color, alpha=0.95, zorder=3)
    ax_top.fill_between(dates, pts, alpha=0.09, color=color)
    ax_top.axhline(avg, color=GOLD, linestyle='--', linewidth=1.4,
                   label=f"Avg  {avg:.1f} pts/game")
    ax_top.set_title(stat_label, color=TEXT, fontsize=12, pad=8)
    ax_top.set_ylabel("Points", color=TEXT)
    ax_top.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax_top.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                  framealpha=0.6, fontsize=9)
    # Thin out x-tick labels so they don't crowd
    ticks = ax_top.get_xticks()
    step  = max(1, len(dates) // 12)
    ax_top.set_xticks(range(0, len(dates), step))
    ax_top.set_xticklabels(dates[::step], rotation=45, fontsize=8, ha='right')

    # Player name watermark (top-left)
    ax_top.text(0.02, 0.96, full_name.upper(),
                transform=ax_top.transAxes,
                ha='left', va='top', color=color,
                fontsize=13, fontweight='bold')
    _fsr_badge(ax_top, overall, color)

    # ── Bottom: FSR sliding window ────────────────────────────────────────────
    _style_ax(ax_bot)
    ax_bot.axhspan(80, 108, color='#103b2e', alpha=0.20)
    ax_bot.axhspan(60,  80, color='#4b3d12', alpha=0.14)
    ax_bot.plot(dates, scores, linewidth=2.4, color=ACCENT,
                label=f"Predictability Score ({win}-game window)")
    ax_bot.axhline(overall, color=color, linestyle='--', linewidth=1.2,
                   label=f"Season FSR: {overall:.1f}")
    ax_bot.axhline(80, color=ELITE,    linestyle=':', linewidth=1.0, label="Elite  (80)")
    ax_bot.axhline(60, color=VOLATILE, linestyle=':', linewidth=1.0, label="Volatile (60)")
    ax_bot.set_title("FSR Predictability Score™", color=TEXT, fontsize=12, pad=8)
    ax_bot.set_ylabel("Score (0-100)", color=TEXT)
    ax_bot.set_xlabel(f"{SEASON} game date", color=TEXT)
    ax_bot.set_ylim(0, 108)
    ax_bot.yaxis.set_major_locator(mticker.MultipleLocator(20))
    step = max(1, len(dates) // 12)
    ax_bot.set_xticks(range(0, len(dates), step))
    ax_bot.set_xticklabels(dates[::step], rotation=45, fontsize=8, ha='right')
    ax_bot.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                  framealpha=0.6, fontsize=9)

    return overall


# ── Build one matchup chart ───────────────────────────────────────────────────

def build_matchup(matchup: dict):
    p1      = matchup['player1']
    p2      = matchup['player2']
    stat    = matchup['stat']
    outfile = os.path.join(OUTPUT_DIR, matchup['filename'])

    # Fetch data
    name1, dates1, pts1 = fetch_pts_series(p1['name'])
    time.sleep(2)
    name2, dates2, pts2 = fetch_pts_series(p2['name'])

    # Build figure
    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5), facecolor=BG)
    for ax in axes.flatten():
        ax.set_facecolor(PANEL)

    fsr1 = _plot_panel(axes[0][0], axes[1][0], name1, dates1, pts1, p1['color'])
    fsr2 = _plot_panel(axes[0][1], axes[1][1], name2, dates2, pts2, p2['color'])

    # ── Main title ────────────────────────────────────────────────────────────
    fig.suptitle(matchup['title'],
                 color=TEXT, fontsize=16, fontweight='bold', y=1.01)

    # ── FSR comparison subtitle ───────────────────────────────────────────────
    diff = fsr1 - fsr2
    lbl  = matchup['subtitle_label']
    if abs(diff) >= 1.0:
        winner = name1.split()[-1] if diff > 0 else name2.split()[-1]
        w_color = p1['color'] if diff > 0 else p2['color']
        sub = (f"{lbl}:  {name1.split()[-1]} {fsr1:.1f}  vs  {name2.split()[-1]} {fsr2:.1f}"
               f"  |  MORE PREDICTABLE: {winner.upper()} (+{abs(diff):.1f} FSR pts)")
    else:
        sub = (f"{lbl}:  {name1.split()[-1]} {fsr1:.1f}  vs  {name2.split()[-1]} {fsr2:.1f}"
               f"  |  ESSENTIALLY EQUAL")

    fig.text(0.5, 0.975, sub,
             ha='center', color=GOLD, fontsize=12, fontweight='bold')
    fig.text(0.5, 0.007,
             "Predictability Score™  ·  k=0.5 (sports)  ·  "
             "Raw PTS series (top) + sliding 10-game FSR window (bottom)  ·  2025-26 NBA season",
             ha='center', color=SUB, fontsize=9)

    plt.tight_layout(rect=[0, 0.025, 1, 0.97])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.savefig(outfile, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print(f"  ✓  Saved → {outfile}")
    return fsr1, fsr2


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 60)
    print('  NBA MVP FSR Charts  |  2025-26 Season')
    print('=' * 60)

    for m in MATCHUPS:
        print(f"\n── {m['title']}")
        try:
            f1, f2 = build_matchup(m)
            print(f"  FSR: {m['player1']['name'].split()[-1]} {f1:.1f}  |  "
                  f"{m['player2']['name'].split()[-1]} {f2:.1f}")
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(3)

    print('\nDone.')
