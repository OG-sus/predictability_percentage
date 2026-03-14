from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
import time
import math
import os
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


def fetch_gamelog_with_retry(player_id, season, retries=3):
    """
    Attempts to fetch game logs with a retry loop and custom headers.
    """
    for i in range(retries):
        try:
            log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season,
                timeout=60,
                headers=HEADERS
            ).get_data_frames()[0]
            return log
        except Exception as e:
            print(f"  [Attempt {i + 1}] Error fetching {season} data: {e}")
            if i < retries - 1:
                wait = (i + 1) * 5  # 5s, 10s, 15s — exponential-ish backoff
                print(f"  Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                raise e


def get_nba_player_stats(player_name, stat_type, num_games=82):
    """
    Fetches game-by-game stats and calculates the Predictability Score.
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

    # 2. Fetch game logs
    try:
        current_season = "2025-26"
        print(f"Fetching {current_season} logs...")
        gamelogs = fetch_gamelog_with_retry(player_id, current_season)

        # Removed 2024-25 data fetch to speed up searches

        if stat_type.upper() not in gamelogs.columns:
            print(f"Error: Stat type '{stat_type}' not found.")
            return

        stats = gamelogs.head(num_games)[stat_type.upper()].tolist()
        stats.reverse()  # Chronological order

        if not stats:
            print("No stats found to process.")
            return

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
        print("\n---------------------------------\n")

        # 5. Sliding Window Analysis
        print("Running Sliding Window Analysis...")
        window_size = 10
        results = calculate_sliding_window(stats, window_size, k=k_factor_sports)

        scores = [r['score'] for r in results]
        scores = [None] * (window_size - 1) + scores

        # Plotting
        plt.figure(figsize=(12, 8))

        plt.subplot(2, 1, 1)
        plt.plot(stats, marker='o', linestyle='-', color='#1d428a', alpha=0.7, label=f'{player_name} {stat_type}')
        plt.axhline(y=simple_avg, color='gray', linestyle='--', label='Average')
        plt.title(f"{player_name} - {stat_type} Performance")
        plt.ylabel(stat_type)
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.subplot(2, 1, 2)
        plt.plot(scores, color='#c8102e', linewidth=2, label='Predictability Score (10-Game Window)')
        plt.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
        plt.axhline(y=60, color='orange', linestyle='--', label='Volatile')
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