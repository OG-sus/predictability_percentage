import requests
from bs4 import BeautifulSoup, Comment
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
    Returns a random set of headers to mimic a real browser and avoid simple bot
    detection rules on the sports‑reference network.
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
    Performs a search on sports-reference and returns a canonical CBB player
    page URL if one is found.  The search endpoint is shared across the network,
    so the parsing logic is identical to the MLB generator.
    """
    search_name = unidecode.unidecode(player_name).lower()
    search_url = f"https://www.sports-reference.com/search/search.fcgi?search={search_name.replace(' ', '+')}"

    headers = get_headers()
    print(f"Searching for {player_name}...")

    try:
        response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code == 429:
            print("Rate limited (429). Waiting 10 seconds...")
            time.sleep(10)
            response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"Error: Could not access Sports-Reference search (Status: {response.status_code})")
            return None

        # Redirect straight to a player page?
        if "/cbb/players" in response.url and "/search/" not in response.url:
            return response.url

        soup = BeautifulSoup(response.content, 'html.parser')
        players_section = soup.find('div', id='players')
        if not players_section:
            # fallback to generic search-item blocks
            search_items = soup.find_all('div', class_='search-item')
            if search_items:
                link = search_items[0].find('a')
                if link and link.get('href'):
                     return f"https://www.sports-reference.com{link['href']}"

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

        player_url = f"https://www.sports-reference.com{link['href']}"
        return player_url

    except Exception as e:
        print(f"Connection error: {e}")
        return None


def get_cbb_player_stats(player_name, stat_type, num_games=30, year=2026):
    """
    Fetches game‑by‑game stats for a college basketball player by scraping the CBB
    portion of sports-reference.  The caller can request the most recent N games
    from a given year (season end year).
    """

    print(f"\n--- Fetching {stat_type} data for {player_name} (last {num_games} games of {year}) ---")

    player_url = get_player_url(player_name)
    if not player_url:
        return

    headers = get_headers()

    # try a dedicated gamelog page first
    gamelog_url = player_url.rstrip('.html') + f"/gamelog/{year}"
    print(f"Attempting to fetch game logs from: {gamelog_url}")
    response = requests.get(gamelog_url, headers=headers, timeout=10)
    if response.status_code != 200:
        # fall back to the player page itself
        print("Couldn't reach gamelog page, falling back to player page.")
        response = requests.get(player_url, headers=headers, timeout=10)
    time.sleep(2)

    if response.status_code != 200:
        print(f"Error: Failed to fetch page (Status: {response.status_code})")
        return

    content = response.content
    soup = BeautifulSoup(content, 'html.parser')

    # sports-reference often hides tables inside comments
    table_html = None
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        if 'id="gamelog"' in comment:
            table_html = comment
            break

    if not table_html:
        table_div = soup.find('div', id='all_gamelog')
        if table_div:
            table_html = str(table_div)

    try:
        if table_html:
            tables = pd.read_html(StringIO(table_html))
        else:
            tables = pd.read_html(StringIO(content.decode('utf-8', errors='replace')))
    except ValueError:
        print("No tables found on page.")
        return

    df = None
    for t in tables:
        if 'Date' in t.columns and 'Opp' in t.columns:
            df = t
            break

    if df is None:
        print("Could not identify a valid game log table.")
        return

    # clean up repeated header rows and non‑game rows
    df = df[df['Date'] != 'Date']
    df = df[df['Date'].notna()]

    if stat_type not in df.columns:
        print(f"Error: Stat type '{stat_type}' not found.")
        print(f"Available stats: {', '.join(df.columns.tolist())}")
        return

    df[stat_type] = pd.to_numeric(df[stat_type], errors='coerce').fillna(0)
    stats = df.head(num_games)[stat_type].astype(int).tolist()
    stats.reverse()

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

        scores = [r['score'] for r in results]
        scores = [None] * (window_size - 1) + scores

        # Plotting
        plt.figure(figsize=(12, 8))

        plt.subplot(2, 1, 1)
        plt.plot(stats, marker='o', linestyle='-', color='#1d428a', alpha=0.7,
                 label=f'{player_name} {stat_type}')
        plt.axhline(y=avg_stat, color='gray', linestyle='--', label='Average')
        plt.title(f"{player_name} - {stat_type} Performance ({year-1}-{str(year)[-2:]})")
        plt.ylabel(stat_type)
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.subplot(2, 1, 2)
        plt.plot(scores, color='#c8102e', linewidth=2,
                 label=f'Predictability Score ({window_size}-Game Window)')
        plt.axhline(y=80, color='green', linestyle='--', label='Elite Stability')
        plt.axhline(y=60, color='orange', linestyle='--', label='Volatile')
        plt.title("Stability Analysis")
        plt.ylabel("Score (0-100)")
        plt.xlabel("Game Number")
        plt.ylim(0, 105)
        plt.legend()
        plt.grid(True, alpha=0.3)

        output_dir = os.path.join("static", "images", "cbb_charts")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        filename = f"{player_name.replace(' ', '_')}_{stat_type}_analysis.png"
        filepath = os.path.join(output_dir, filename)

        plt.tight_layout()
        plt.savefig(filepath)
        plt.close()
        print(f"Chart saved to {filepath}")


if __name__ == "__main__":
    print("CBB Player Stat Generator")
    print("-----------------------------------------------")
    print("Common Stats: PTS, FGM, FGA, 3P, 3PA, FT, FT%, REB, AST, STL, BLK")

    while True:
        player_name = input("\nEnter College Basketball Player Name (or 'q' to quit): ").strip()
        if player_name.lower() == 'q':
            break

        stat_type = input("Enter Stat Type (e.g., PTS, AST): ").strip().upper()
        try:
            year = int(input("Season end year (default 2026): ") or "2026")
        except ValueError:
            year = 2026

        try:
            num_games = int(input("Number of recent games to fetch (default 30): ") or "30")
        except ValueError:
            num_games = 30

        get_cbb_player_stats(player_name, stat_type, num_games, year)
        time.sleep(1)
