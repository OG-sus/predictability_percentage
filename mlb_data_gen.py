import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import unidecode
import random
import os
from io import StringIO
import matplotlib.pyplot as plt
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

def get_headers():
    """
    Returns a random set of headers to mimic a real browser and avoid 403 errors.
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.google.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

def get_player_url(player_name):
    """
    Searches for a player on Baseball-Reference.com and returns their page URL.
    """
    search_name = unidecode.unidecode(player_name).lower()
    search_url = f"https://www.baseball-reference.com/search/search.fcgi?search={search_name.replace(' ', '+')}"
    
    headers = get_headers()
    print(f"Searching for {player_name}...")
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 429:
            print("Rate limited (429). Waiting 10 seconds...")
            time.sleep(10)
            response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"Error: Could not access Baseball-Reference search (Status: {response.status_code})")
            return None

        # If the search redirects directly to a player page, we're golden.
        if "players" in response.url and "/search/" not in response.url:
            return response.url

        # Otherwise, we need to parse the search results page.
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the "Players" section in search results
        players_section = soup.find('div', id='players')
        if not players_section:
            # Sometimes it's just a list without the ID if only one category matches
            search_items = soup.find_all('div', class_='search-item')
            if search_items:
                link = search_items[0].find('a')
                if link and link.get('href'):
                     return f"https://www.baseball-reference.com{link['href']}"
            
            print(f"No players found for '{player_name}' in search results.")
            return None
            
        first_result = players_section.find('div', class_='search-item')
        if not first_result:
            print(f"No player items found for '{player_name}'.")
            return None

        link = first_result.find('a')
        if not link or not link.get('href'):
            print("Could not find a valid player link in search results.")
            return None
            
        player_url = f"https://www.baseball-reference.com{link['href']}"
        return player_url
        
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def get_mlb_player_stats(player_name, stat_type, num_games=20, year=2026):
    """
    Fetches game-by-game stats for a given MLB player by scraping Baseball-Reference.com.
    """
    print(f"\n--- Fetching {stat_type} data for {player_name} (last {num_games} games of {year}) ---")

    player_url = get_player_url(player_name)
    if not player_url:
        return

    # Determine if the player is a pitcher or batter to get the correct game log table
    # A simple heuristic: if the URL has /pitch/ it's a pitcher page.
    is_pitcher = "/pitch/" in player_url
    
    # Construct the game log URL
    # e.g., https://www.baseball-reference.com/players/o/ohtansh01-pitch.shtml
    # becomes https://www.baseball-reference.com/players/gl.fcgi?id=ohtansh01&t=p&year=2023
    
    # Extract ID from URL like /players/j/judgeaa01.shtml
    try:
        player_id = player_url.split('/')[-1].split('.')[0]
        # If it has -pitch or -bat suffix, remove it (though usually it's just the ID)
        if '-' in player_id:
            player_id = player_id.split('-')[0]
            
        log_type = 'p' if is_pitcher else 'b'
        gamelog_url = f"https://www.baseball-reference.com/players/gl.fcgi?id={player_id}&t={log_type}&year={year}"
        
        print(f"Found player page. Fetching game logs from: {gamelog_url}")
        
        headers = get_headers()
        response = requests.get(gamelog_url, headers=headers, timeout=10)
        time.sleep(2) # Be polite

        if response.status_code != 200:
            print(f"Error: Failed to fetch game logs (Status: {response.status_code})")
            return

        # Find the correct game log table
        table_id = "pitching_gamelogs" if is_pitcher else "batting_gamelogs"
        
        # Use pandas to easily read the HTML table
        # We need to pass the HTML string to read_html
        tables = pd.read_html(StringIO(response.text), attrs={'id': table_id})
        
        if not tables:
            # Fallback: sometimes the table ID is different or hidden
            print(f"Could not find the game log table '{table_id}'. Trying generic search...")
            tables = pd.read_html(StringIO(response.text))
            if not tables:
                print("No tables found on page.")
                return
        
        # Iterate through tables to find one with 'Date' and 'Opp'
        df = None
        for t in tables:
            if 'Date' in t.columns and 'Opp' in t.columns:
                df = t
                break
        
        if df is None:
            print("Could not identify a valid game log table.")
            return
        
        # Data cleaning
        # Remove header rows that are repeated within the table
        df = df[df['Date'] != 'Date'] 
        # Filter out rows that are not actual games (e.g., team totals, month totals)
        # Valid games usually have a number in 'Gtm' or 'Rk'
        if 'Gtm' in df.columns:
            df = df[df['Gtm'].notna()]
        
        df = df.dropna(subset=['Date'])

        # Handle column name mismatches (e.g., 'SO' might be 'SO' or 'K')
        if stat_type == 'K' and 'SO' in df.columns:
            stat_type = 'SO'
            
        if stat_type not in df.columns:
            print(f"Error: Stat type '{stat_type}' not found.")
            print(f"Available stats: {', '.join(df.columns.tolist())}")
            return

        # Convert stat column to numeric, coercing errors to NaN, then fill with 0
        df[stat_type] = pd.to_numeric(df[stat_type], errors='coerce').fillna(0)

        # Get the most recent games
        stats = df.head(num_games)[stat_type].astype(int).tolist()
        stats.reverse() # Chronological order

        output_string = ", ".join(map(str, stats))

        print(f"\nSuccessfully fetched {len(stats)} game stats for {player_name}.")
        print(f"Stat Type: {stat_type.upper()}")
        print("\n--- COPY THE DATA BELOW FOR YOUR DASHBOARD ---\n")
        print(output_string)
        print("\n----------------------------------------------\n")
        
        if stats:
            # Predictability Calculation
            k_factor_sports = 0.5
            score = calculate_predictability(stats, k=k_factor_sports)
            avg_stat = sum(stats) / len(stats)

            print(f"Predictability Score: {score:.2f}")
            print(f"Suggested Target (Average {stat_type.upper()}): {round(avg_stat, 2)}")
            print("\n----------------------------------------------\n")

            # Sliding Window Analysis
            print("Running Sliding Window Analysis...")
            window_size = min(10, len(stats))
            results = calculate_sliding_window(stats, window_size, k=k_factor_sports)

            scores_list = [r['score'] for r in results]
            scores_list = [None] * (window_size - 1) + scores_list

            # Plotting
            plt.figure(figsize=(12, 8))

            plt.subplot(2, 1, 1)
            plt.plot(stats, marker='o', linestyle='-', color='#002D62', alpha=0.7,
                     label=f'{player_name} {stat_type}')
            plt.axhline(y=avg_stat, color='gray', linestyle='--', label='Average')
            plt.title(f"{player_name} - {stat_type} Performance ({year})")
            plt.ylabel(stat_type)
            plt.legend()
            plt.grid(True, alpha=0.3)

            plt.subplot(2, 1, 2)
            plt.plot(scores_list, color='#c8102e', linewidth=2,
                     label=f'Predictability Score ({window_size}-Game Window)')
            plt.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
            plt.axhline(y=60, color='orange', linestyle='--', label='Volatile')
            plt.title("Stability Analysis")
            plt.ylabel("Score (0-100)")
            plt.xlabel("Game Number")
            plt.ylim(0, 105)
            plt.legend()
            plt.grid(True, alpha=0.3)

            output_dir = os.path.join("static", "images", "mlb_charts")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            filename = f"{player_name.replace(' ', '_')}_{stat_type}_analysis.png"
            filepath = os.path.join(output_dir, filename)

            plt.tight_layout()
            plt.savefig(filepath)
            plt.close()
            print(f"Chart saved to {filepath}")

    except Exception as e:
        print(f"An error occurred while parsing game logs: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("MLB Player Stat Generator for Predictability API")
    print("------------------------------------------------")
    print("Common Batting Stats: H, HR, R, RBI, SO, BB, SB")
    print("Common Pitching Stats: IP, H, R, ER, BB, SO, HR")
    
    while True:
        player_name = input("\nEnter MLB Player Name (e.g., Shohei Ohtani, Aaron Judge, or 'q' to quit): ").strip()
        if player_name.lower() == 'q':
            break
        
        stat_type = input("Enter Stat Type (e.g., H, HR, SO): ").strip().upper()
        
        try:
            year = int(input("Enter Season Year (default 2026): ") or "2026")
        except ValueError:
            print("Invalid year. Using default of 2026.")
            year = 2026
            
        try:
            num_games = int(input("Number of recent games to fetch (default 20): ") or "20")
        except ValueError:
            print("Invalid number of games. Using default of 20.")
            num_games = 20

        get_mlb_player_stats(player_name, stat_type, num_games, year)
        time.sleep(2) # Be polite to the website
