#!/usr/bin/env python3
"""
cbb_watchlist.py — NCAA Tournament Round of 64 Watchlist Generator
===================================================================
Pulls today's tournament games from ESPN's live scoreboard API,
fetches rosters for every team playing, grabs season averages for
each player, scores them with FSR Predictability Score™, and prints
a ranked watchlist sorted by scoring average.

Usage:
  python scripts/cbb_watchlist.py                    # auto-detect today's games
  python scripts/cbb_watchlist.py --date 20260320    # specific date (YYYYMMDD)
  python scripts/cbb_watchlist.py --top 5            # top N players per team (default 3)
  python scripts/cbb_watchlist.py --out watchlist.csv
"""

import argparse
import csv
import sys
import time
import os
from datetime import datetime

# Allow running from scripts/ subdirectory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from cbb_data_gen import get_cbb_stats_raw
from fsr import calculate_predictability

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0'})

# Stat label order returned by the ESPN overview endpoint
ESPN_LABELS = ['GP', 'MIN', 'FG%', '3P%', 'FT%', 'REB', 'AST', 'BLK', 'STL', 'PF', 'TO', 'PTS']


# ---------------------------------------------------------------------------
# ESPN API helpers
# ---------------------------------------------------------------------------

def get_todays_tournament_games(date_str=None):
    """
    Returns list of (game_name, home_team_dict, away_team_dict) for today's
    tournament games. Each team dict has 'id', 'displayName', 'abbreviation'.
    """
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')

    url = (
        f'https://site.api.espn.com/apis/site/v2/sports/basketball/'
        f'mens-college-basketball/scoreboard?dates={date_str}&groups=100'
    )
    try:
        r = SESSION.get(url, timeout=10)
        r.raise_for_status()
        events = r.json().get('events', [])
    except Exception as e:
        print(f'Error fetching scoreboard: {e}')
        return []

    games = []
    for ev in events:
        comp = ev.get('competitions', [{}])[0]
        teams = comp.get('competitors', [])
        if len(teams) < 2:
            continue
        home = next((t['team'] for t in teams if t.get('homeAway') == 'home'), teams[0]['team'])
        away = next((t['team'] for t in teams if t.get('homeAway') == 'away'), teams[1]['team'])
        games.append((ev.get('name', ''), home, away))
    return games


def get_roster(team_id, top_n=3):
    """
    Returns list of player dicts: {name, id, pts, reb, ast, gp}
    sorted by scoring average, top_n only.
    """
    url = (
        f'https://site.api.espn.com/apis/common/v3/sports/basketball/'
        f'mens-college-basketball/teams/{team_id}/roster'
    )
    try:
        r = SESSION.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    players = []
    for pg in data.get('positionGroups', []):
        for a in pg.get('athletes', []):
            players.append({'name': a.get('displayName', ''), 'id': a.get('id', '')})

    # Enrich with season averages
    enriched = []
    for p in players:
        stats = get_season_averages(p['id'])
        p.update(stats)
        enriched.append(p)
        time.sleep(0.1)

    # Sort by points, return top N
    enriched.sort(key=lambda x: x.get('pts', 0), reverse=True)
    return enriched[:top_n]


def get_season_averages(athlete_id):
    """Returns dict with pts, reb, ast, gp from ESPN overview endpoint."""
    url = (
        f'https://site.api.espn.com/apis/common/v3/sports/basketball/'
        f'mens-college-basketball/athletes/{athlete_id}/overview'
    )
    empty = {'pts': 0.0, 'reb': 0.0, 'ast': 0.0, 'gp': 0}
    try:
        r = SESSION.get(url, timeout=8)
        if r.status_code != 200:
            return empty
        data = r.json()
        stats = data.get('statistics', {})
        splits = stats.get('splits', [])
        if not splits:
            return empty
        # First split is current season
        vals = splits[0].get('stats', [])
        d = dict(zip(ESPN_LABELS, vals))
        return {
            'pts': float(d.get('PTS', 0) or 0),
            'reb': float(d.get('REB', 0) or 0),
            'ast': float(d.get('AST', 0) or 0),
            'gp':  int(float(d.get('GP', 0) or 0)),
        }
    except Exception:
        return empty


def get_fsr_score(player_name, stat='PTS', num_games=30, year=2026):
    """Pull game log and return FSR predictability score. Returns None on failure."""
    try:
        stats = get_cbb_stats_raw(player_name, stat, num_games=num_games, year=year)
        if len(stats) < 4:
            return None
        return round(calculate_predictability(stats, k=0.5), 2)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description='NCAA Tournament Day 1 Watchlist')
    ap.add_argument('--date', default=None, help='Date YYYYMMDD (default: today)')
    ap.add_argument('--top', type=int, default=3, help='Top N players per team (default 3)')
    ap.add_argument('--num-games', type=int, default=30)
    ap.add_argument('--year', type=int, default=2026)
    ap.add_argument('--out', default='cbb_watchlist.csv')
    ap.add_argument('--no-fsr', action='store_true', help='Skip FSR game log fetch (faster, no predictability score)')
    args = ap.parse_args()

    print('=' * 60)
    print('NCAA Tournament Watchlist — Powered by FSR Predictability Score™')
    print('=' * 60)

    date_str = args.date or datetime.now().strftime('%Y%m%d')
    print(f'\nFetching games for {date_str}...')
    games = get_todays_tournament_games(date_str)

    if not games:
        print('No tournament games found for this date. Try --date YYYYMMDD')
        sys.exit(1)

    print(f'Found {len(games)} games ({len(games) * 2} teams)\n')

    rows = []
    for game_name, home, away in games:
        print(f'\n── {game_name} ──')
        for team in (away, home):
            t_name = team.get('displayName', '')
            t_id   = team.get('id', '')
            print(f'  {t_name} (fetching top {args.top} players)...')

            players = get_roster(t_id, top_n=args.top)
            if not players:
                print(f'    Could not fetch roster.')
                continue

            for p in players:
                name = p['name']
                pts  = p.get('pts', 0)
                reb  = p.get('reb', 0)
                ast  = p.get('ast', 0)
                gp   = p.get('gp', 0)

                fsr_score = None
                if not args.no_fsr and gp >= 5:
                    fsr_score = get_fsr_score(name, 'PTS', args.num_games, args.year)

                fsr_display = f'{fsr_score:.1f}' if fsr_score is not None else 'N/A'
                print(f'    {name:<28} {pts:.1f}pts  {reb:.1f}reb  {ast:.1f}ast  FSR:{fsr_display}')

                rows.append({
                    'game':      game_name,
                    'team':      t_name,
                    'player':    name,
                    'pts_avg':   pts,
                    'reb_avg':   reb,
                    'ast_avg':   ast,
                    'gp':        gp,
                    'fsr_pts':   fsr_score if fsr_score is not None else '',
                })

    # Sort full list by pts_avg descending
    rows.sort(key=lambda x: x['pts_avg'], reverse=True)

    # Write CSV
    fields = ['game', 'team', 'player', 'pts_avg', 'reb_avg', 'ast_avg', 'gp', 'fsr_pts']
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f'\n{"=" * 60}')
    print(f'TOP 10 PLAYERS TO WATCH TODAY')
    print(f'{"=" * 60}')
    for r in rows[:10]:
        fsr = f"FSR:{r['fsr_pts']}" if r['fsr_pts'] != '' else ''
        print(f"  {r['player']:<28} {r['pts_avg']:.1f}pts  {r['team']}  {fsr}")

    print(f'\nFull watchlist saved → {args.out}')
    print(f'Total players: {len(rows)}')


if __name__ == '__main__':
    main()

