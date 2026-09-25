"""
LoL MSI 2025 — FSR Pipeline
Data: Leaguepedia (lol.fandom.com) via free MediaWiki Cargo API
Runs FSR on team performance signals to find who's structurally dominant vs. hot.

Usage:
    python lol_msi_gen.py
"""

import math
import time
import json
import urllib.request
import urllib.parse
import sys

# ---------------------------------------------------------------------------
# FSR core  (mirrors fsr.py — no Numba dependency for standalone use)
# ---------------------------------------------------------------------------

def fsr(values, k=1.0):
    arr = [v for v in values if v is not None and not math.isnan(float(v))]
    n = len(arr)
    if n < 2:
        return None
    mean = sum(arr) / n
    if abs(mean) < 1e-9:
        return None
    variance = sum((x - mean) ** 2 for x in arr) / (n - 1)
    stdev = math.sqrt(variance)
    cv = stdev / mean
    return round(max(0.0, min(100.0, 100 * math.exp(-k * abs(cv)))), 1)

# ---------------------------------------------------------------------------
# Leaguepedia API helper
# ---------------------------------------------------------------------------

API_BASE = "https://lol.fandom.com/api.php"
OVERVIEW = "2026 Mid-Season Invitational"  # change to "2025 Mid-Season Invitational" for historical data

def lp_query(tables, fields, where, limit=500, retries=4):
    params = urllib.parse.urlencode({
        "action": "cargoquery",
        "tables": tables,
        "fields": fields,
        "where": where,
        "limit": str(limit),
        "format": "json",
    })
    url = f"{API_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "FSR-Research/1.0"})

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            if "error" in data and "ratelimited" in data["error"].get("code", ""):
                wait = 8 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            return [row["title"] for row in data.get("cargoquery", [])]
        except Exception as e:
            print(f"  API error (attempt {attempt+1}): {e}")
            time.sleep(5)
    return []

# ---------------------------------------------------------------------------
# Fetch series-level match results
# ---------------------------------------------------------------------------

def fetch_series():
    print(f"Fetching series results for: {OVERVIEW}")
    rows = lp_query(
        tables="MatchSchedule",
        fields="Team1,Team2,Winner,Team1Score,Team2Score,DateTime_UTC,Tab,BestOf",
        where=f"OverviewPage='{OVERVIEW}'",
    )
    print(f"  Found {len(rows)} series")
    return rows

# ---------------------------------------------------------------------------
# Fetch game-level scoreboard data
# ---------------------------------------------------------------------------

def fetch_games():
    print(f"Fetching game-level data for: {OVERVIEW}")
    time.sleep(6)
    rows = lp_query(
        tables="ScoreboardGames",
        fields="Team1,Team2,WinTeam,Team1Gold,Team2Gold,Team1Kills,Team2Kills,"
               "Team1Dragons,Team2Dragons,Team1Barons,Team2Barons,Gamelength,Tab",
        where=f"OverviewPage='{OVERVIEW}'",
    )
    if rows:
        print(f"  Found {len(rows)} individual games")
    else:
        print("  No game-level data available — using series data only")
    return rows

# ---------------------------------------------------------------------------
# Build per-team signal arrays from series
# ---------------------------------------------------------------------------

def build_series_signals(series):
    """
    From series data extract per-team:
      - win/loss array (1=win, 0=loss)
      - score differential per series (team_score - opponent_score)
      - games_played per series (total games: team_score + opponent_score)
    """
    teams = {}

    for row in series:
        t1 = row.get("Team1", "").strip()
        t2 = row.get("Team2", "").strip()
        winner = row.get("Winner", "")
        t1s = row.get("Team1Score") or ""
        t2s = row.get("Team2Score") or ""
        tab  = row.get("Tab", "")

        if not t1 or not t2:
            continue
        try:
            s1 = int(t1s)
            s2 = int(t2s)
        except (ValueError, TypeError):
            continue

        t1_win = 1 if winner == "1" else 0
        t2_win = 1 if winner == "2" else 0
        t1_diff = s1 - s2
        t2_diff = s2 - s1
        games_total = s1 + s2

        for team, win, diff in [(t1, t1_win, t1_diff), (t2, t2_win, t2_diff)]:
            if team not in teams:
                teams[team] = {"wins": [], "diff": [], "games": [], "tabs": []}
            teams[team]["wins"].append(win)
            teams[team]["diff"].append(diff)
            teams[team]["games"].append(games_total)
            teams[team]["tabs"].append(tab)

    return teams

def build_game_signals(games):
    """From individual game data, build per-team gold, kills, dragons arrays."""
    teams = {}

    for row in games:
        t1  = (row.get("Team1") or "").strip()
        t2  = (row.get("Team2") or "").strip()
        win = (row.get("WinTeam") or "").strip()

        def safe_int(v):
            try: return int(v)
            except: return None

        g1  = safe_int(row.get("Team1Gold"))
        g2  = safe_int(row.get("Team2Gold"))
        k1  = safe_int(row.get("Team1Kills"))
        k2  = safe_int(row.get("Team2Kills"))
        d1  = safe_int(row.get("Team1Dragons"))
        d2  = safe_int(row.get("Team2Dragons"))
        b1  = safe_int(row.get("Team1Barons"))
        b2  = safe_int(row.get("Team2Barons"))
        gl  = row.get("Gamelength") or ""

        # Parse gamelength "mm:ss" -> minutes
        try:
            parts = str(gl).split(":")
            gmin = int(parts[0]) + int(parts[1]) / 60
        except:
            gmin = None

        def add(team, vals_dict):
            if team not in teams:
                teams[team] = {k: [] for k in vals_dict}
            for k, v in vals_dict.items():
                if v is not None:
                    teams[team].setdefault(k, []).append(v)

        if t1 and t2:
            gold_diff = (g1 - g2) if g1 is not None and g2 is not None else None
            add(t1, {"gold": g1, "gold_diff": gold_diff, "kills": k1,
                     "dragons": d1, "barons": b1, "gamelength": gmin,
                     "win": 1 if win == t1 else 0})
            neg_diff = (-gold_diff) if gold_diff is not None else None
            add(t2, {"gold": g2, "gold_diff": neg_diff, "kills": k2,
                     "dragons": d2, "barons": b2, "gamelength": gmin,
                     "win": 1 if win == t2 else 0})

    return teams

# ---------------------------------------------------------------------------
# FSR table builder
# ---------------------------------------------------------------------------

K_BINARY   = 3.0   # win/loss arrays — higher k, tighter scoring
K_STANDARD = 1.0
K_SPREAD   = 1.5   # game-count / gamelength spread

def series_fsr_table(series_signals):
    rows = []
    for team, sig in series_signals.items():
        series_count = len(sig["wins"])
        if series_count < 2:
            continue

        win_rate   = round(sum(sig["wins"]) / series_count * 100, 1)
        avg_diff   = round(sum(sig["diff"]) / series_count, 2)
        avg_games  = round(sum(sig["games"]) / series_count, 2)

        # FSR on score differential (how consistently dominant)
        diff_fsr  = fsr(sig["diff"], k=K_STANDARD)
        # FSR on game count per series (3-0 sweep vs 3-2 grind — lower games = more dominant)
        # Invert: fewer games = more dominant. Use (BestOf - games) as dominance signal
        dominance = [5 - g for g in sig["games"]]  # for BO5: sweep=2, 3-1=1, 3-2=0
        dom_fsr   = fsr(dominance, k=K_SPREAD)

        row = {
            "Team": team,
            "Series": series_count,
            "Win %": win_rate,
            "Avg Score Diff": avg_diff,
            "Score Diff FSR": diff_fsr,
            "Dominance FSR":  dom_fsr,   # consistency of winning cleanly
            "Avg Games/Series": avg_games,
        }
        rows.append(row)

    rows.sort(key=lambda r: (r.get("Score Diff FSR") or 0) + (r.get("Dominance FSR") or 0), reverse=True)
    return rows

def game_fsr_table(game_signals):
    rows = []
    for team, sig in game_signals.items():
        game_count = len(sig.get("win", []))
        if game_count < 3:
            continue

        row = {
            "Team": team,
            "Games": game_count,
            "Win %": round(sum(sig.get("win",[])) / game_count * 100, 1) if sig.get("win") else None,
            "Gold Diff FSR":    fsr(sig.get("gold_diff", []), k=K_STANDARD),
            "Kills FSR":        fsr(sig.get("kills", []), k=K_STANDARD),
            "Dragon FSR":       fsr(sig.get("dragons", []), k=K_SPREAD),
            "Baron FSR":        fsr(sig.get("barons", []), k=K_SPREAD),
            "Gamelength FSR":   fsr(sig.get("gamelength", []), k=K_SPREAD),
            "Avg Gold Diff":    round(sum(sig.get("gold_diff",[])) / len(sig["gold_diff"]), 0) if sig.get("gold_diff") else None,
        }
        # Composite = mean of available FSR scores
        fsr_cols = ["Gold Diff FSR", "Kills FSR", "Dragon FSR", "Baron FSR", "Gamelength FSR"]
        vals = [row[c] for c in fsr_cols if row.get(c) is not None]
        row["Composite FSR"] = round(sum(vals) / len(vals), 1) if vals else None
        rows.append(row)

    rows.sort(key=lambda r: r.get("Composite FSR") or 0, reverse=True)
    return rows

# ---------------------------------------------------------------------------
# Pretty print
# ---------------------------------------------------------------------------

def print_table(rows, title):
    if not rows:
        print(f"\n  No data for: {title}")
        return
    print(f"\n{'='*65}")
    print(f" {title}")
    print(f"{'='*65}")
    if not rows:
        return
    keys = list(rows[0].keys())
    widths = {k: max(len(str(k)), max((len(str(r.get(k, ""))) for r in rows), default=0)) for k in keys}
    header = "  ".join(str(k).ljust(widths[k]) for k in keys)
    print(header)
    print("-" * len(header))
    for r in rows:
        print("  ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys))

# ---------------------------------------------------------------------------
# Insight blurb
# ---------------------------------------------------------------------------

def print_insights(series_rows, game_rows):
    print(f"\n{'='*65}")
    print(" KEY INSIGHTS (FSR Analysis)")
    print(f"{'='*65}")

    if series_rows:
        # Most structurally consistent WINNER (win rate >= 50% + highest combined FSR)
        winners = [r for r in series_rows if (r.get("Win %") or 0) >= 50]
        if winners:
            top = winners[0]
            print(f"\n Most structurally dominant team:  {top['Team']}")
            print(f"   Win %: {top['Win %']}%  |  Score Diff FSR: {top.get('Score Diff FSR')}  |  Dominance FSR: {top.get('Dominance FSR')}")
        else:
            print("\n  No team has >= 50% win rate yet (early in tournament)")

        # "Hot" team: high win% but low score-diff FSR (winning inconsistently)
        hot_candidates = [
            r for r in series_rows
            if (r.get("Win %") or 0) >= 50 and r.get("Score Diff FSR") is not None
        ]
        hot_candidates.sort(key=lambda r: (r.get("Win %") or 0) - (r.get("Score Diff FSR") or 0), reverse=True)
        if hot_candidates:
            hot = hot_candidates[0]
            print(f"\n Hottest team (winning but inconsistent margins): {hot['Team']}")
            print(f"   Win %: {hot['Win %']}%  |  Score Diff FSR: {hot.get('Score Diff FSR')}")
            print(f"   Signal: results outpacing structural consistency → regression risk")

        # Most consistent loser (low FSR teams losing — opposite story)
        losers = [r for r in series_rows if (r.get("Win %") or 0) < 50 and r.get("Score Diff FSR") is not None]
        losers.sort(key=lambda r: r.get("Score Diff FSR") or 0)
        if losers:
            v = losers[0]
            print(f"\n Most volatile team:  {v['Team']}")
            print(f"   Win %: {v['Win %']}%  |  Score Diff FSR: {v.get('Score Diff FSR')}")

    if game_rows:
        top = game_rows[0]
        print(f"\n Most consistent game-level performer: {top['Team']}")
        print(f"   Composite FSR: {top.get('Composite FSR')}  |  Gold Diff FSR: {top.get('Gold Diff FSR')}  |  Win %: {top.get('Win %')}%")

    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    series = fetch_series()
    if not series:
        print("No series data found. Exiting.")
        sys.exit(1)

    games = fetch_games()

    series_signals = build_series_signals(series)
    series_rows    = series_fsr_table(series_signals)

    print_table(series_rows, "TEAM FSR — MSI 2025 (Series Level)")

    game_rows = []
    if games:
        game_signals = build_game_signals(games)
        game_rows    = game_fsr_table(game_signals)
        print_table(game_rows, "TEAM FSR — MSI 2025 (Game Level)")

    print_insights(series_rows, game_rows)

    # Save
    import csv, os
    out = os.path.join(os.path.dirname(__file__), "lol_msi_fsr_results.csv")
    if series_rows:
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=series_rows[0].keys())
            writer.writeheader()
            writer.writerows(series_rows)
        print(f"Saved series results to {out}")

if __name__ == "__main__":
    main()
