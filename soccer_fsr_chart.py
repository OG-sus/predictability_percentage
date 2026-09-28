#!/usr/bin/env python3
"""
soccer_fsr_chart.py — International Football FSR Chart
=======================================================
Pulls all international match results from martj42/international-football-results
(GitHub, free, no key). Runs FSR on goals scored + goal differential per team.
YouTube-ready 1920x1080 dark chart.

Usage:
    python soccer_fsr_chart.py "USA" "Paraguay"
    python soccer_fsr_chart.py "Canada" "Bosnia and Herzegovina"
"""

import sys
import json
import urllib.request
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── CONFIG ────────────────────────────────────────────────────────────────────
TEAM_A   = sys.argv[1] if len(sys.argv) > 1 else "United States"
TEAM_B   = sys.argv[2] if len(sys.argv) > 2 else "Paraguay"
N_GAMES  = 30
WINDOW   = 10
K        = 0.8
OUT      = f"soccer_fsr_{TEAM_A.lower().replace(' ','_')}_vs_{TEAM_B.lower().replace(' ','_')}.png"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

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

# Team color pairs — primary used for FSR line, accent for bar avg line
# Colors chosen to be visually distinct from each other on dark background
TEAM_COLORS = {
    "United States":          ("#4FC3F7", "#3C3B6E"),   # light blue
    "USA":                    ("#4FC3F7", "#3C3B6E"),
    "Paraguay":               ("#EF5350", "#FFFFFF"),   # red
    "Canada":                 ("#FF6F00", "#FFFFFF"),   # amber/orange
    "Bosnia and Herzegovina": ("#42A5F5", "#FFCE00"),   # blue
    "Qatar":                  ("#AB47BC", "#FFFFFF"),   # purple
    "Switzerland":            ("#EF5350", "#FFFFFF"),   # red
}

def team_color(name):
    return TEAM_COLORS.get(name, ("#29b6f6", "#f06292"))[0]

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
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.6)

# ── ESPN TEAM ID MAP ──────────────────────────────────────────────────────────
ESPN_IDS = {
    "United States": (660, [
        ("concacaf.nations.league", [2024, 2025, 2026, 2023, 2022, 2021]),
        ("conmebol.america",        [2024, 2021, 2019, 2016]),
        ("concacaf.gold.cup",       [2025, 2023, 2021, 2019, 2017]),
        ("fifa.worldq.concacaf",    [2026, 2022]),
        ("fifa.world",              [2026, 2022]),
    ]),
    "Paraguay": (210, [
        ("fifa.worldq.conmebol",    [2026, 2025, 2024, 2023, 2022, 2021, 2020]),
        ("conmebol.america",        [2024, 2021, 2019, 2016]),
        ("conmebol.worldq",         [2026, 2022]),
    ]),
    "Canada": (206, [
        ("fifa.worldq.concacaf",    [2020]),
        ("concacaf.nations.league", [2024, 2023, 2022, 2019]),
        ("conmebol.america",        [2024]),
        ("fifa.world",              [2022]),
    ]),
    "Bosnia and Herzegovina": (452, [
        ("fifa.worldq.uefa",        [2025, 2021]),
    ]),
    "Bosnia-Herzegovina": (452, [
        ("fifa.worldq.uefa",        [2025, 2021]),
    ]),
    "Qatar": (4398, [
        ("afc.asian.cup",           [2023, 2019]),
        ("fifa.worldq.afc",         [2023]),
    ]),
    "Switzerland": (475, [
        ("uefa.euro",               [2024, 2020]),
        ("fifa.worldq.uefa",        [2025, 2021]),
        ("fifa.world",              [2022, 2018]),
    ]),
}

# ── FETCH DATA ────────────────────────────────────────────────────────────────
def fetch_espn_results(team_name):
    if team_name not in ESPN_IDS:
        print(f'  WARNING: {team_name} not in ESPN ID map')
        return []
    team_id, league_seasons = ESPN_IDS[team_name]
    all_results = []
    seen = set()
    for league, seasons in league_seasons:
        for season in seasons:
            url = f'{ESPN_BASE}/{league}/teams/{team_id}/schedule?season={season}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            try:
                r = urllib.request.urlopen(req, timeout=8)
                d = json.loads(r.read())
            except:
                continue
            for e in d.get('events', []):
                comp = e.get('competitions', [{}])[0]
                if not comp.get('status', {}).get('type', {}).get('completed', False):
                    continue
                competitors = comp.get('competitors', [])
                me  = next((c for c in competitors if str(c.get('id')) == str(team_id)), None)
                opp = next((c for c in competitors if str(c.get('id')) != str(team_id)), None)
                if not me or not opp:
                    continue
                try:
                    gf = me.get('score');  ga = opp.get('score')
                    if isinstance(gf, dict): gf = gf.get('value', 0)
                    if isinstance(ga, dict): ga = ga.get('value', 0)
                    key = (e.get('date','')[:10], str(opp.get('id','')))
                    if key in seen:
                        continue
                    seen.add(key)
                    all_results.append({
                        'gf': int(float(gf)), 'ga': int(float(ga)),
                        'opp': opp.get('team', {}).get('displayName', '?'),
                        'date': e.get('date', '')[:10],
                    })
                except:
                    pass
    all_results.sort(key=lambda x: x['date'])
    return all_results[-N_GAMES:]

def get_team_series(team_name):
    raw = fetch_espn_results(team_name)
    goals    = [r['gf'] for r in raw]
    conceded = [r['ga'] for r in raw]
    gdiff    = [r['gf'] - r['ga'] for r in raw]
    dates    = [r['date'] for r in raw]
    results  = ['W' if r['gf'] > r['ga'] else ('D' if r['gf'] == r['ga'] else 'L') for r in raw]
    return goals, conceded, gdiff, dates, results

print(f'Processing {TEAM_A}...')
a_goals, a_con, a_gdiff, a_dates, a_res = get_team_series(TEAM_A)
print(f'  {len(a_goals)} matches  |  last 5: {" ".join(a_res[-5:])}')

print(f'Processing {TEAM_B}...')
b_goals, b_con, b_gdiff, b_dates, b_res = get_team_series(TEAM_B)
print(f'  {len(b_goals)} matches  |  last 5: {" ".join(b_res[-5:])}')

if len(a_goals) < 3 or len(b_goals) < 3:
    print(f'ERROR: insufficient data — {TEAM_A}: {len(a_goals)}, {TEAM_B}: {len(b_goals)}')
    import sys; sys.exit(1)

# FSR scores
a_fsr_goals = calculate_predictability(a_goals, k=K)
b_fsr_goals = calculate_predictability(b_goals, k=K)
a_fsr_gdiff = calculate_predictability(a_gdiff, k=K)
b_fsr_gdiff = calculate_predictability(b_gdiff, k=K)

print(f'\n  {TEAM_A} Goals FSR: {a_fsr_goals:.1f}  GDiff FSR: {a_fsr_gdiff:.1f}')
print(f'  {TEAM_B} Goals FSR: {b_fsr_goals:.1f}  GDiff FSR: {b_fsr_gdiff:.1f}')

# Rolling FSR
def rolling_fsr(vals, window=WINDOW):
    if len(vals) < window + 1:
        return [], []
    sw = calculate_sliding_window(vals, window, k=K)
    return list(range(window - 1, len(vals))), [r['score'] for r in sw]

a_rx, a_ry = rolling_fsr(a_goals)
b_rx, b_ry = rolling_fsr(b_goals)

# ── CHART ─────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
fig.patch.set_facecolor(BG)

gs = gridspec.GridSpec(
    2, 3,
    width_ratios=[2, 2, 1],
    height_ratios=[1.2, 1],
    hspace=0.45, wspace=0.25,
    left=0.05, right=0.97,
    top=0.84, bottom=0.10,
)

ax_a   = fig.add_subplot(gs[0, 0])   # Team A goals
ax_b   = fig.add_subplot(gs[0, 1])   # Team B goals
ax_fsr = fig.add_subplot(gs[1, :2])  # Rolling FSR both teams
ax_sc  = fig.add_subplot(gs[:, 2])   # Score card

for ax in [ax_a, ax_b, ax_fsr, ax_sc]:
    style_ax(ax)

ca = team_color(TEAM_A)
cb = team_color(TEAM_B)
xs = list(range(len(a_goals)))
xs_b = list(range(len(b_goals)))

def bar_colors(goals, conceded):
    out = []
    for g, c in zip(goals, conceded):
        if g > c:   out.append(GREEN)
        elif g < c: out.append(RED)
        else:       out.append(GOLD)
    return out

# Team A goals bars
ax_a.bar(xs, a_goals, color=bar_colors(a_goals, a_con), alpha=0.85, width=0.7)
ax_a.set_title(f'{TEAM_A}  —  Goals Scored (Last {N_GAMES} Matches)',
               color=WHITE, fontsize=11, fontfamily='monospace', pad=6)
ax_a.set_ylabel('Goals', color=TEXT, fontsize=9, fontfamily='monospace')
ax_a.text(0.99, 0.97, f'FSR: {a_fsr_goals:.1f}  [{score_label(a_fsr_goals)}]',
          transform=ax_a.transAxes, ha='right', va='top',
          color=score_color(a_fsr_goals), fontsize=10, fontfamily='monospace', fontweight='bold')
# Avg line
avg_a = sum(a_goals) / len(a_goals)
ax_a.axhline(avg_a, color=ca, linewidth=1.2, linestyle='--', alpha=0.6,
             label=f'Avg: {avg_a:.1f}')
ax_a.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=9, loc='upper left')

# Team B goals bars
ax_b.bar(xs_b, b_goals, color=bar_colors(b_goals, b_con), alpha=0.85, width=0.7)
ax_b.set_title(f'{TEAM_B}  —  Goals Scored (Last {N_GAMES} Matches)',
               color=WHITE, fontsize=11, fontfamily='monospace', pad=6)
ax_b.set_ylabel('Goals', color=TEXT, fontsize=9, fontfamily='monospace')
ax_b.text(0.99, 0.97, f'FSR: {b_fsr_goals:.1f}  [{score_label(b_fsr_goals)}]',
          transform=ax_b.transAxes, ha='right', va='top',
          color=score_color(b_fsr_goals), fontsize=10, fontfamily='monospace', fontweight='bold')
avg_b = sum(b_goals) / len(b_goals) if b_goals else 0
ax_b.axhline(avg_b, color=cb, linewidth=1.2, linestyle='--', alpha=0.6,
             label=f'Avg: {avg_b:.1f}')
ax_b.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=9, loc='upper left')

# Rolling FSR panel
if a_rx:
    ax_fsr.fill_between(a_rx, a_ry, alpha=0.08, color=ca)
    ax_fsr.plot(a_rx, a_ry, color=ca, linewidth=2.2, label=f'{TEAM_A} FSR  {a_fsr_goals:.1f}')
    ax_fsr.scatter([a_rx[-1]], [a_ry[-1]], color=ca, s=60, zorder=5, edgecolors=BG, linewidths=1.5)
if b_rx:
    ax_fsr.fill_between(b_rx, b_ry, alpha=0.08, color=cb)
    ax_fsr.plot(b_rx, b_ry, color=cb, linewidth=2.2, label=f'{TEAM_B} FSR  {b_fsr_goals:.1f}')
    ax_fsr.scatter([b_rx[-1]], [b_ry[-1]], color=cb, s=60, zorder=5, edgecolors=BG, linewidths=1.5)

ax_fsr.axhline(70, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.5)
ax_fsr.axhline(45, color=GOLD,  linewidth=0.8, linestyle=':', alpha=0.5)
ax_fsr.text(0.02, 0.685, 'CONSISTENT', color=GREEN, fontsize=8, alpha=0.6,
            fontfamily='monospace', transform=ax_fsr.transAxes)
ax_fsr.text(0.02, 0.445, 'MODERATE',   color=GOLD,  fontsize=8, alpha=0.6,
            fontfamily='monospace', transform=ax_fsr.transAxes)
ax_fsr.set_ylim(0, 105)
# Explicit xlim so rolling window always fills the full panel width
n_matches = max(len(a_goals), len(b_goals))
if a_rx or b_rx:
    x_start = min((a_rx[0] if a_rx else n_matches), (b_rx[0] if b_rx else n_matches))
    ax_fsr.set_xlim(x_start - 0.5, n_matches - 0.5)
ax_fsr.set_ylabel('FSR Score', color=TEXT, fontsize=10, fontfamily='monospace')
ax_fsr.set_title(f'{WINDOW}-Match Rolling FSR — Goals Scored Consistency',
                 color=WHITE, fontsize=11, fontfamily='monospace', pad=6)
leg = ax_fsr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=10, loc='upper right')
for t in leg.get_texts(): t.set_fontfamily('monospace')

# ── SCORE CARD ────────────────────────────────────────────────────────────────
ax_sc.set_xlim(0, 1); ax_sc.set_ylim(0, 1)
ax_sc.set_xticks([]); ax_sc.set_yticks([])
ax_sc.text(0.5, 0.975, 'FSR VERDICT', ha='center', va='top',
           fontsize=11, color=DIM, fontfamily='monospace', fontweight='bold')

TEAM_ABBREV = {
    "United States": "USA", "Canada": "CAN", "Paraguay": "PAR",
    "Bosnia and Herzegovina": "BIH", "Qatar": "QAT", "Switzerland": "SUI",
}
def abbrev(name): return TEAM_ABBREV.get(name, name[:3].upper())

badges = [
    (abbrev(TEAM_A), a_fsr_goals, ca),
    (abbrev(TEAM_B), b_fsr_goals, cb),
]
slot_h = 0.22
tops   = [0.92, 0.92 - slot_h - 0.03]

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
               fontsize=26, fontweight='bold', color=sc, fontfamily='monospace', zorder=3)
    ax_sc.text(0.5, mid_y - 0.04, label, ha='center', va='center',
               fontsize=9, fontweight='bold', color=color, fontfamily='monospace', zorder=3)
    ax_sc.text(0.5, mid_y - 0.09, score_label(score), ha='center', va='center',
               fontsize=8, color=sc, fontfamily='monospace', zorder=3)

# Form summary
form_y = 0.35
for label, res, color in [(abbrev(TEAM_A), a_res[-5:], ca),
                            (abbrev(TEAM_B), b_res[-5:], cb)]:
    ax_sc.text(0.5, form_y + 0.04, f'{label} (last 5)', ha='center', fontsize=8,
               color=DIM, fontfamily='monospace')
    fx = 0.12
    for r in res:
        rc = GREEN if r == 'W' else (RED if r == 'L' else GOLD)
        ax_sc.text(fx, form_y - 0.01, r, ha='center', fontsize=11,
                   fontweight='bold', color=rc, fontfamily='monospace')
        fx += 0.18
    form_y -= 0.13

avg_note = f'Avg goals: {avg_a:.1f} vs {avg_b:.1f}'
ax_sc.text(0.5, 0.05, avg_note, ha='center', fontsize=8,
           color=DIM, fontfamily='monospace')

# ── HEADER ────────────────────────────────────────────────────────────────────
tomorrow = (datetime.now()).strftime('%B %d, %Y')
fig.text(0.5, 0.960,
         f'{TEAM_A.upper()}  vs  {TEAM_B.upper()}  —  FSR PREDICTABILITY ANALYSIS',
         ha='center', fontsize=18, fontweight='bold', color=WHITE, fontfamily='monospace')
fig.text(0.5, 0.925,
         f'Goals Scored Consistency  ·  {N_GAMES}-Match Sample  ·  FSR Predictability Score™  ·  Data: FIFA International Results',
         ha='center', fontsize=10, color=DIM, fontfamily='monospace')

fig.text(0.97, 0.005,
         f'international-football-results  ·  {datetime.now().strftime("%Y-%m-%d")}  ·  predictability-api.com',
         ha='right', fontsize=7.5, color='#2a2a45', fontfamily='monospace')

plt.savefig(OUT, dpi=100, facecolor=BG)
plt.close()
print(f'\nSaved: {OUT}')
