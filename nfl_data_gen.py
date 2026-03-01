import pandas as pd
import time
import string
import requests
from io import StringIO

def get_player_url(player_name):
    """
    Generates a Pro-Football-Reference URL for a given player.
    This is a best-guess heuristic and might not be perfect for all names.
    """
    # Sanitize name: remove punctuation, make lowercase
    name_clean = player_name.translate(str.maketrans('', '', string.punctuation)).lower()
    parts = name_clean.split()
    
    if len(parts) < 2:
        return None, "Invalid name format. Please use 'First Last'."

    last_name = parts[-1]
    first_name = parts[0]
    
    # URL format: First letter of last name / First 4 of last + First 2 of first + "00"
    last_initial = last_name[0]
    url_slug = last_name[:4].capitalize() + first_name[:2].capitalize() + "00"
    
    url = f"https://www.pro-football-reference.com/players/{last_initial}/{url_slug}/gamelog/"
    return url, url_slug

def get_nfl_player_stats_from_web(player_name, stat_type, year=2025):
    """
    Fetches game-by-game stats for a given NFL player by scraping Pro-Football-Reference.
    """
    print(f"\n--- Fetching {stat_type} data for {player_name} ({year} Season) via Web Scraping ---")

    try:
        # 1. Generate the player's URL
        player_url, slug = get_player_url(player_name)
        if not player_url:
            print(f"Error: {slug}")
            return
            
        full_url = f"{player_url}{year}/"
        print(f"Attempting to fetch data from: {full_url}")

        # 2. Fetch the page content with headers to avoid 403
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(full_url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error: Failed to fetch page (Status Code: {response.status_code})")
            return

        # 3. Parse the table
        # Use StringIO to avoid the FutureWarning
        tables = pd.read_html(StringIO(response.text))
        
        if not tables:
            print("No tables found on the page.")
            return

        # The main game log is usually the first table
        gamelog_df = tables[0]

        # 4. Clean up Columns
        # Handle MultiIndex columns if they exist
        if isinstance(gamelog_df.columns, pd.MultiIndex):
            # Flatten columns: join levels with '_' but skip empty levels
            new_cols = []
            for col in gamelog_df.columns.values:
                # col is a tuple like ('Unnamed: 0_level_0', 'Date') or ('Passing', 'Yds')
                # We want just 'Date' or 'Passing_Yds'
                parts = [str(c) for c in col if "Unnamed" not in str(c) and "level" not in str(c)]
                new_cols.append("_".join(parts).strip("_"))
            gamelog_df.columns = new_cols
        
        # Debug: Print columns to help user if stat not found
        # print(f"Available columns: {gamelog_df.columns.tolist()}")

        # 5. Filter Rows
        # Find the Date column (it might be named 'Date' or something similar)
        date_col = next((col for col in gamelog_df.columns if 'Date' in col), None)
        
        if not date_col:
            print("Error: Could not find a 'Date' column in the table.")
            return

        # Remove header rows (where Date column equals 'Date')
        gamelog_df = gamelog_df[gamelog_df[date_col] != 'Date']
        # Remove rows with NaN date
        gamelog_df = gamelog_df[gamelog_df[date_col].notna()]

        # 6. Find the Stat Column
        # Normalize input stat_type (e.g., 'rec_yds' -> 'Rec_Yds' or 'Receiving_Yds')
        # Common mappings for PFR
        stat_map = {
            'rec_yds': 'Receiving_Yds',
            'pass_yds': 'Passing_Yds',
            'rush_yds': 'Rushing_Yds',
            'rec': 'Receiving_Rec',
            'receptions': 'Receiving_Rec'
        }
        
        target_stat = stat_map.get(stat_type.lower(), stat_type)
        
        # Fuzzy match for column name
        matching_cols = [col for col in gamelog_df.columns if target_stat.lower() in col.lower()]
        
        if not matching_cols:
            print(f"Error: Stat type '{stat_type}' (mapped to '{target_stat}') not found in the table.")
            print(f"Available columns: {', '.join(gamelog_df.columns.tolist())}")
            return
            
        # Prefer the shortest match (e.g., 'Yds' vs 'Yds_/A') if multiple
        stat_col = min(matching_cols, key=len)
        print(f"Found matching stat column: '{stat_col}'")

        # 7. Extract Data
        # Convert stat column to numeric, coercing errors to NaN, then fill NaNs with 0
        stats = pd.to_numeric(gamelog_df[stat_col], errors='coerce').fillna(0).astype(int).tolist()

        # Format as comma-separated string
        output_string = ", ".join(map(str, stats))

        print(f"\nSuccessfully fetched {len(stats)} game stats.")
        print(f"Stat Type: {stat_col}")
        print("\n--- COPY THE DATA BELOW FOR YOUR DASHBOARD ---\n")
        print(output_string)
        print("\n----------------------------------------------\n")
        
        if stats:
            avg_stat = sum(stats) / len(stats)
            print(f"Suggested Target (Average): {round(avg_stat, 2)}")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("NFL Player Stat Generator (Web Scraping Edition)")
    print("------------------------------------------------")
    print("This script scrapes Pro-Football-Reference.com.")
    print("Common Stats: Rec_Yds, Pass_Yds, Rush_Yds, TD")
    
    while True:
        player_name = input("\nEnter NFL Player Name (e.g., Patrick Mahomes, or 'q' to quit): ").strip()
        if player_name.lower() == 'q':
            break
        
        stat_type = input("Enter Stat Type (e.g., Pass_Yds, Rush_Yds): ").strip()
        
        year_input = input("Enter Season Year (default 2025): ").strip()
        year = int(year_input) if year_input else 2025

        get_nfl_player_stats_from_web(player_name, stat_type, year)
        time.sleep(1) # Be polite
