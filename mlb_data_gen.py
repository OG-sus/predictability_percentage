import time
import random
import requests
import pandas as pd
import unidecode
from fsr import calculate_predictability

try:
    from pybaseball import playerid_lookup, statcast_batter, statcast_pitcher
    PYBASEBALL_AVAILABLE = True
except ImportError:
    PYBASEBALL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Session-based scraping helpers (fallback only)
# ---------------------------------------------------------------------------

CURRENT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
]

def make_session():
    """Create a requests session that mimics a real browser visit."""
    session = requests.Session()
    ua = random.choice(CURRENT_USER_AGENTS)
    session.headers.update({
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })
    # Prime the session with a homepage visit to get cookies
    try:
        session.get('https://www.baseball-reference.com/', timeout=10)
        time.sleep(random.uniform(2, 4))
    except Exception:
        pass
    return session

# ---------------------------------------------------------------------------
# Primary path: pybaseball (no scraping, no 403s)
# ---------------------------------------------------------------------------

def _get_stats_via_pybaseball(player_name, stat_type, num_games=20, year=2025):
    """Uses pybaseball Statcast data — no scraping required."""
    parts = player_name.strip().split()
    if len(parts) < 2:
        print("Please enter first and last name.")
        return

    last, first = parts[-1], parts[0]
    print(f"Looking up player ID for {first} {last}...")

    try:
        lookup = playerid_lookup(last, first)
    except Exception as e:
        print(f"Player lookup failed: {e}")
        return

    if lookup.empty:
        print(f"No player found for '{player_name}'. Check spelling.")
        return

    lookup = lookup.sort_values('mlb_played_last', ascending=False)
    row = lookup.iloc[0]
    mlbam_id = int(row['key_mlbam'])
    print(f"Found: {row.get('name_first','')} {row.get('name_last','')} (MLBAM ID: {mlbam_id})")

    start_date = f"{year}-03-01"
    end_date   = f"{year}-11-30"

    try:
        try:
            data = statcast_batter(start_date, end_date, player_id=mlbam_id)
        except Exception:
            data = statcast_pitcher(start_date, end_date, player_id=mlbam_id)

        if data is None or data.empty:
            print(f"No Statcast data found for {year}. Try a different year.")
            return

        data['game_date'] = pd.to_datetime(data['game_date'])

        EVENT_FILTERS = {
            'HR': lambda df: df[df['events'] == 'home_run'].groupby('game_date').size(),
            'H':  lambda df: df[df['events'].isin(['single', 'double', 'triple', 'home_run'])].groupby('game_date').size(),
            'SO': lambda df: df[df['events'] == 'strikeout'].groupby('game_date').size(),
            'K':  lambda df: df[df['events'] == 'strikeout'].groupby('game_date').size(),
            'BB': lambda df: df[df['events'] == 'walk'].groupby('game_date').size(),
        }

        stat_upper = stat_type.upper()
        if stat_upper in EVENT_FILTERS:
            game_stats = EVENT_FILTERS[stat_upper](data).reset_index()
            game_stats.columns = ['game_date', stat_upper]
        else:
            print(f"Stat '{stat_type}' not directly available via Statcast.")
            print("Available: H, HR, SO/K, BB")
            return

        game_stats = game_stats.sort_values('game_date', ascending=True)
        stats = game_stats[stat_upper].astype(int).tail(num_games).tolist()

    except Exception as e:
        print(f"Statcast data error: {e}")
        return

    _print_results(player_name, stat_upper, stats)


# ---------------------------------------------------------------------------
# Fallback path: session-based scraping
# ---------------------------------------------------------------------------

def _get_stats_via_scraping(player_name, stat_type, num_games=20, year=2025):
    """Falls back to session-based scraping if pybaseball is unavailable."""
    from bs4 import BeautifulSoup
    stat_upper = stat_type.upper()
    search_name = unidecode.unidecode(player_name).lower().replace(' ', '+')
    search_url  = f"https://www.baseball-reference.com/search/search.fcgi?search={search_name}"

    session = make_session()
    print(f"Searching Baseball-Reference for {player_name}...")

    try:
        resp = session.get(search_url, timeout=15)
        time.sleep(random.uniform(2, 4))

        if resp.status_code == 403:
            print("Baseball-Reference is blocking automated requests (403).")
            print("Tip: Install pybaseball for a reliable alternative: pip install pybaseball")
            return
        if resp.status_code == 429:
            print("Rate limited — waiting 15s...")
            time.sleep(15)
            resp = session.get(search_url, timeout=15)
        if resp.status_code != 200:
            print(f"Error: Status {resp.status_code}")
            return

        if "players" in resp.url and "/search/" not in resp.url:
            player_url = resp.url
        else:
            soup  = BeautifulSoup(resp.content, 'html.parser')
            items = soup.find_all('div', class_='search-item')
            if not items:
                print(f"No results for '{player_name}'.")
                return
            link = items[0].find('a')
            if not link:
                print("Could not parse search results.")
                return
            player_url = f"https://www.baseball-reference.com{link['href']}"

        is_pitcher = "/pitch/" in player_url
        player_id  = player_url.split('/')[-1].split('.')[0].split('-')[0]
        log_type   = 'p' if is_pitcher else 'b'
        gamelog_url = f"https://www.baseball-reference.com/players/gl.fcgi?id={player_id}&t={log_type}&year={year}"

        print(f"Fetching game log from: {gamelog_url}")
        resp2 = session.get(gamelog_url, timeout=15)
        time.sleep(random.uniform(3, 5))

        if resp2.status_code != 200:
            print(f"Failed to fetch game log (Status: {resp2.status_code})")
            return

        table_id = "pitching_gamelogs" if is_pitcher else "batting_gamelogs"
        tables = pd.read_html(resp2.content, attrs={'id': table_id})
        if not tables:
            tables = pd.read_html(resp2.content)
        if not tables:
            print("No tables found.")
            return

        df = None
        for t in tables:
            if 'Date' in t.columns and 'Opp' in t.columns:
                df = t
                break
        if df is None:
            print("Could not identify game log table.")
            return

        df = df[df['Date'] != 'Date'].dropna(subset=['Date'])
        if stat_upper == 'K' and 'SO' in df.columns:
            stat_upper = 'SO'
        if stat_upper not in df.columns:
            print(f"Stat '{stat_upper}' not found. Available: {', '.join(df.columns.tolist())}")
            return

        df[stat_upper] = pd.to_numeric(df[stat_upper], errors='coerce').fillna(0)
        stats = df.head(num_games)[stat_upper].astype(int).tolist()
        stats.reverse()

    except Exception as e:
        print(f"Scraping error: {e}")
        return

    _print_results(player_name, stat_upper, stats)


def _print_results(player_name, stat_type, stats):
    if not stats:
        print("No stats returned.")
        return

    k_factor_sports = 0.5
    score = calculate_predictability(stats, k=k_factor_sports)
    simple_avg = sum(stats) / len(stats)

    print(f"\nSuccessfully fetched {len(stats)} game stats for {player_name}.")
    print(f"Stat Type: {stat_type.upper()}")
    print("\n--- COPY THE DATA BELOW FOR YOUR DASHBOARD ---\n")
    print(", ".join(map(str, stats)))
    print("\n----------------------------------------------\n")
    print(f"Predictability Score: {score:.2f}")
    print(f"Simple Average: {simple_avg:.2f}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_mlb_player_stats(player_name, stat_type, num_games=20, year=2025):
    print(f"\n--- Fetching {stat_type} data for {player_name} (last {num_games} games of {year}) ---")
    if PYBASEBALL_AVAILABLE:
        _get_stats_via_pybaseball(player_name, stat_type, num_games, year)
    else:
        print("pybaseball not installed — falling back to web scraping (may be blocked).")
        print("Run: pip install pybaseball  for a reliable alternative.")
        _get_stats_via_scraping(player_name, stat_type, num_games, year)


if __name__ == "__main__":
    print("MLB Player Stat Generator for Predictability API")
    print("------------------------------------------------")
    print("Stats available via pybaseball: H, HR, SO/K, BB")
    print("Stats available via scraping:   H, HR, R, RBI, SO, BB, SB (may be blocked)")

    while True:
        player_name = input("\nEnter MLB Player Name (e.g., Shohei Ohtani, Aaron Judge, or 'q' to quit): ").strip()
        if player_name.lower() == 'q':
            break
        stat_type = input("Enter Stat Type (e.g., H, HR, SO): ").strip().upper()
        try:
            year = int(input("Enter Season Year (default 2025): ") or "2025")
        except ValueError:
            year = 2025
        try:
            num_games = int(input("Number of recent games to fetch (default 20): ") or "20")
        except ValueError:
            num_games = 20
        get_mlb_player_stats(player_name, stat_type, num_games, year)
        time.sleep(2)

