from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
import argparse
import time
import math
import os
from datetime import date
import pandas as pd
from sliding_window import calculate_sliding_window
from fsr import calculate_predictability
import matplotlib.pyplot as plt

# Headers required by NBA Stats API (they block outdated/missing headers)
HEADERS = {
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
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


def fetch_gamelog_with_retry(player_id, season, season_type='Regular Season', retries=3):
    for i in range(retries):
        try:
            log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season,
                season_type_all_star=season_type,
                timeout=60,
                headers=HEADERS
            ).get_data_frames()[0]
            return log
        except Exception as e:
            print(f"  [Attempt {i + 1}] Error fetching {season} {season_type}: {e}")
            if i < retries - 1:
                wait = (i + 1) * 5
                print(f"  Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                raise e


def season_label(start_year):
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def current_season_start(today=None):
    """NBA seasons tip off in October: Oct 2026 onward is 2026-27, before that 2025-26."""
    today = today or date.today()
    return today.year if today.month >= 10 else today.year - 1


def get_nba_player_stats(player_name, stat_type, num_games=82, seasons=2, window_size=10):
    """
    Fetches game-by-game stats and calculates the Predictability Score.
    Combines the last `seasons` seasons (oldest first), so the chart still has a long series in
    the first weeks of a new season - or before it tips off, when the new season has no games yet.
    """
    print(f"\n--- Fetching {stat_type} data for {player_name} (last {num_games} games) ---")

    # 1. Find player ID
    nba_players = players.get_players()
    player_dict = [player for player in nba_players if player_name.lower() in player['full_name'].lower()]

    if not player_dict:
        print(f"Error: Player '{player_name}' not found.")
        return

    player_id = player_dict[0]['id']
    player_name = player_dict[0]['full_name']
    print(f"Found player: {player_name} (ID: {player_id})")

    # 2. Fetch game logs (regular season + playoffs), for each season oldest -> newest
    try:
        newest = current_season_start()
        parts, markers = [], []  # markers: (index in the combined log, label)
        count = 0
        for start in range(newest - seasons + 1, newest + 1):
            season = season_label(start)
            print(f"Fetching {season} regular season logs...")
            try:
                reg_logs = fetch_gamelog_with_retry(player_id, season, 'Regular Season')
            except Exception:
                reg_logs = pd.DataFrame()

            print(f"Fetching {season} playoff logs...")
            try:
                po_logs = fetch_gamelog_with_retry(player_id, season, 'Playoffs')
            except Exception:
                po_logs = pd.DataFrame()

            # The API returns newest-first, so reverse each before combining
            if not reg_logs.empty:
                reg_logs = reg_logs.iloc[::-1].reset_index(drop=True)
                if count:
                    markers.append((count, f"{season} starts"))
                parts.append(reg_logs)
                count += len(reg_logs)
            if not po_logs.empty:
                po_logs = po_logs.iloc[::-1].reset_index(drop=True)
                markers.append((count, f"{season} playoffs"))
                parts.append(po_logs)
                count += len(po_logs)
            print(f"  {season}: regular season {len(reg_logs)} games  |  Playoffs: {len(po_logs)} games")

        if not parts:
            print("No games found for those seasons.")
            return
        gamelogs = pd.concat(parts, ignore_index=True)

        if stat_type.upper() not in gamelogs.columns:
            print(f"Error: Stat type '{stat_type}' not found.")
            return

        # Take last num_games from combined log (already chronological)
        stats = gamelogs.tail(num_games)[stat_type.upper()].tolist()

        if not stats:
            print("No stats found to process.")
            return

        # Shift the season/playoff markers relative to the tail slice
        total_games = len(gamelogs)
        tail_start = max(0, total_games - num_games)
        marks = [(i - tail_start, label) for i, label in markers if i > tail_start]

        # 3. Predictability Calculation
        k_factor_sports = 0.5
        score = calculate_predictability(stats, k=k_factor_sports)
        simple_avg = sum(stats) / len(stats)

        # 4. Format and Print Output
        output_string = ", ".join(map(str, stats))

        print(f"\nSuccessfully fetched {len(stats)} game stats for {player_name}.")
        print(f"Stat Type: {stat_type.upper()}")
        print("\n--- COPY THE RAW DATA BELOW ---\n")
        print(output_string)
        print("\n---------------------------------\n")
        print(f"Predictability Score: {score:.2f}")
        print(f"Simple Average: {simple_avg:.2f}")
        for i, label in marks:
            print(f"{label} at game index: {i}")
        print("\n---------------------------------\n")

        safe = "".join(c if c.isalnum() else "_" for c in player_name).strip("_").lower()
        out_path = os.path.join("output", f"nba_{safe}_{stat_type.lower()}_{len(stats)}games.txt")
        os.makedirs("output", exist_ok=True)
        with open(out_path, "w") as f:
            f.write(output_string)
        print(f"Saved {out_path}  (chart it at window {window_size}, k={k_factor_sports})")

        # 5. Sliding Window Analysis
        print("Running Sliding Window Analysis...")
        results = calculate_sliding_window(stats, window_size, k=k_factor_sports)

        scores = [r['score'] for r in results]
        scores = [None] * (window_size - 1) + scores

        # Plotting
        plt.figure(figsize=(12, 8))

        plt.subplot(2, 1, 1)
        plt.plot(stats, marker='o', linestyle='-', color='#1d428a', alpha=0.7, label=f'{player_name} {stat_type}')
        plt.axhline(y=simple_avg, color='gray', linestyle='--', label='Average')
        for i, label in marks:
            plt.axvline(x=i, color='gold' if 'playoffs' in label else 'gray', linestyle='--', linewidth=1.5, label=label)
        plt.title(f"{player_name} - {stat_type} Performance (Regular Season + Playoffs)")
        plt.ylabel(stat_type)
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.subplot(2, 1, 2)
        plt.plot(scores, color='#c8102e', linewidth=2, label=f'Predictability Score ({window_size}-Game Window)')
        plt.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
        plt.axhline(y=60, color='orange', linestyle='--', label='Volatile')
        for i, label in marks:
            plt.axvline(x=i, color='gold' if 'playoffs' in label else 'gray', linestyle='--', linewidth=1.5, label=label)
        plt.title("Stability Analysis")
        plt.ylabel("Score (0-100)")
        plt.xlabel("Game Number")
        plt.ylim(0, 105)
        plt.legend()
        plt.grid(True, alpha=0.3)

        output_dir = os.path.join("static", "images", "nba_charts")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        filename = f"{player_name.replace(' ', '_')}_{stat_type}_analysis.png"
        filepath = os.path.join(output_dir, filename)

        plt.tight_layout()
        plt.savefig(filepath)
        plt.close()
        print(f"Chart saved to {filepath}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="NBA player game-by-game stat + Predictability Score")
    ap.add_argument("name", nargs="?", help="player name (omit to be asked)")
    ap.add_argument("stat", nargs="?", default="PTS", help="PTS, REB, AST, FG3M, MIN, ... (default PTS)")
    ap.add_argument("--games", type=int, default=250, help="most recent N games (default 250)")
    ap.add_argument("--seasons", type=int, default=3, help="seasons to combine, newest last (default 3)")
    ap.add_argument("--window", type=int, default=10, help="sliding window in games (default 10)")
    args = ap.parse_args()
    if args.name:
        get_nba_player_stats(args.name, args.stat, args.games, args.seasons, args.window)
        raise SystemExit

    print("NBA Player Stat Generator (with Predictability Score)")
    print("----------------------------------------------------")

    while True:
        player_name_input = input("\nEnter NBA Player Name (or 'q' to quit): ").strip()
        if player_name_input.lower() == 'q':
            break

        stat_type_input = input("Enter Stat Type (e.g., PTS, REB, AST): ").strip()

        try:
            num_games_input = int(input("Number of recent games to fetch (default 82): ") or "82")
        except ValueError:
            num_games_input = 82

        get_nba_player_stats(player_name_input, stat_type_input, num_games_input)