import pandas as pd
import time
import string
import unidecode
import requests
from bs4 import BeautifulSoup, Comment

def get_player_url_hockey(player_name):
    """
    Generates a Hockey-Reference.com URL for a given player.
    Example: Connor McDavid -> m/mcdavco01
    """
    # Sanitize name: remove punctuation, make lowercase, handle accents
    name_clean = unidecode.unidecode(player_name.lower())
    parts = name_clean.split()
    
    if len(parts) < 2:
        return None, "Invalid name format. Please use 'First Last'."

    last_name = parts[-1]
    first_name = parts[0]
    
    # URL format: First letter of last name / 5 chars of last + 2 chars of first + "01"
    last_initial = last_name[0]
    url_slug = last_name[:5] + first_name[:2] + "01"
    
    url = f"https://www.hockey-reference.com/players/{last_initial}/{url_slug}/gamelog/"
    return url, url_slug

def get_nhl_player_stats_from_web(player_name, stat_type, year=2026):
    """
    Fetches game-by-game stats for a given NHL player by scraping Hockey-Reference.com.
    This version handles tables hidden inside HTML comments and filters summary rows more robustly.
    """
    print(f"\n--- Fetching {stat_type} data for {player_name} ({year-1}-{year}) via Web Scraping ---")

    try:
        # 1. Generate the player's URL
        player_url, slug = get_player_url_hockey(player_name)
        if not player_url:
            print(f"Error: {slug}")
            return
            
        full_url = f"{player_url}{year}"
        print(f"Attempting to fetch data from: {full_url}")

        # 2. Fetch page content with requests
        response = requests.get(full_url)
        response.raise_for_status() # Raise an exception for bad status codes

        # 3. Use BeautifulSoup to find the commented-out table
        soup = BeautifulSoup(response.content, 'html.parser')
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        
        table_html = None
        for comment in comments:
            if 'id="gamelog"' in comment:
                table_html = comment
                break
        
        if not table_html:
            table_div = soup.find('div', id='all_gamelog')
            if table_div:
                table_html = str(table_div)
            else:
                raise ValueError("Could not find the game log table on the page (ID: gamelog or all_gamelog).")

        # 4. Use pandas to read the extracted HTML
        gamelog_df = pd.read_html(table_html)[0]

        # 5. Clean up the DataFrame
        # Drop the top-level header (often duplicated)
        gamelog_df.columns = gamelog_df.columns.droplevel(0) 
        
        # Robustly filter out header and summary rows
        # Keep only rows where 'Rk' is a number (game rank) AND 'Date' is not empty
        gamelog_df = gamelog_df[pd.to_numeric(gamelog_df['Rk'], errors='coerce').notna()]
        gamelog_df = gamelog_df[gamelog_df['Date'].notna()]
        
        stat_map = {
            "goals": "G", "assists": "A", "points": "PTS",
            "plusminus": "+/-", "shots": "S", "hits": "HIT", "blocks": "BLK"
        }
        
        col_name = stat_map.get(stat_type.lower())
        
        if not col_name or col_name not in gamelog_df.columns:
            print(f"Error: Stat type '{stat_type}' not found. Supported: {', '.join(stat_map.keys())}")
            return
            
        print(f"Found matching stat column: '{col_name}'")

        stats = pd.to_numeric(gamelog_df[col_name], errors='coerce').fillna(0).astype(int).tolist()

        output_string = ", ".join(map(str, stats))

        print(f"\nSuccessfully fetched {len(stats)} game stats.")
        print(f"Stat Type: {stat_type.capitalize()}")
        print("\n--- COPY THE DATA BELOW FOR YOUR DASHBOARD ---\n")
        print(output_string)
        print("\n----------------------------------------------\n")
        
        if stats:
            avg_stat = sum(stats) / len(stats)
            print(f"Suggested Target (Average): {round(avg_stat, 2)}")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Web scraping can be fragile. The site structure may have changed, or the player URL guess was incorrect.")

if __name__ == "__main__":
    try:
        import requests
        import bs4
        import unidecode
    except ImportError:
        print("This script requires 'requests', 'beautifulsoup4', and 'unidecode'.")
        print("Please install them by running: pip install requests beautifulsoup4 unidecode")
        exit()

    print("NHL Player Stat Generator (Web Scraping v4)")
    print("------------------------------------------------")
    print("Common Stats: goals, assists, points, shots, hits, blocks, plusminus")
    
    while True:
        player_name = input("\nEnter NHL Player Name (e.g., Connor McDavid, or 'q' to quit): ").strip()
        if player_name.lower() == 'q':
            break
        
        stat_type = input("Enter Stat Type (e.g., goals, shots): ").strip()
        
        year_input = input("Enter End Year of Season (e.g., 2026 for 2025-26, default 2026): ").strip()
        year = int(year_input) if year_input else 2026

        get_nhl_player_stats_from_web(player_name, stat_type, year)
        time.sleep(1)
