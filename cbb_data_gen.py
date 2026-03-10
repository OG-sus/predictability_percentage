import requests
try:
    import cloudscraper
except ImportError:
    cloudscraper = None
from bs4 import BeautifulSoup, Comment
import pandas as pd
import time
import unidecode
import random
import json
from fsr import calculate_predictability


# ---------------------------------------------------------------------------
# cloudscraper-based helpers (bypasses Cloudflare bot detection)
# ---------------------------------------------------------------------------

def make_scraper():
    """Return a scraper session; use cloudscraper when available, else requests.Session."""
    if cloudscraper is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )
        print("Warning: 'cloudscraper' not installed. Using requests fallback session.")
        return session

    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )


# ---------------------------------------------------------------------------
# ESPN API path (primary — no scraping, no 403s)
# ---------------------------------------------------------------------------

def _get_espn_athlete_id(player_name):
    """Search ESPN's v2 search endpoint for a CBB player. Returns (athlete_id, display_name)."""
    query = player_name.replace(' ', '+')
    url = f"https://site.api.espn.com/apis/search/v2?query={query}&limit=10"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None, None
        data = resp.json()

        cbb_id, cbb_name = None, None
        first_id, first_name = None, None

        for group in data.get('results', []):
            if group.get('type') != 'player':
                continue
            for item in group.get('contents', []):
                # Extract numeric athlete ID from uid like "s:40~l:46~a:5041939"
                uid = item.get('uid', '')
                raw_id = None
                if '~a:' in uid:
                    raw_id = uid.split('~a:')[-1]
                elif item.get('id', '').isdigit():
                    raw_id = item['id']

                if not raw_id:
                    continue

                display = item.get('displayName', '')
                league = item.get('defaultLeagueSlug', '')
                desc   = item.get('description', '')

                if first_id is None:
                    first_id, first_name = raw_id, display

                if 'college' in league.lower() or 'ncaa' in desc.lower() or 'college' in desc.lower():
                    cbb_id, cbb_name = raw_id, display
                    break
            if cbb_id:
                break

        return (cbb_id, cbb_name) if cbb_id else (first_id, first_name)
    except Exception:
        pass
    return None, None


ESPN_STAT_MAP = {
    'PTS': 'points',
    'REB': 'rebounds',
    'AST': 'assists',
    'STL': 'steals',
    'BLK': 'blocks',
    'FGM': 'fieldGoalsMade',
    'FGA': 'fieldGoalsAttempted',
    '3PM': 'threePointFieldGoalsMade',
    '3PA': 'threePointFieldGoalsAttempted',
    'FTM': 'freeThrowsMade',
    'FTA': 'freeThrowsAttempted',
    'TO':  'turnovers',
    'MIN': 'minutes',
}

def _get_stats_via_espn(player_name, stat_type, num_games=30, year=2025):
    """Fetches game-by-game CBB stats via ESPN's API — no scraping required."""
    athlete_id, found_name = _get_espn_athlete_id(player_name)
    if not athlete_id:
        print(f"Could not find '{player_name}' on ESPN. Trying scrape fallback...")
        return None

    print(f"Found on ESPN: {found_name} (ID: {athlete_id})")

    espn_key = ESPN_STAT_MAP.get(stat_type.upper())
    if not espn_key:
        print(f"Stat '{stat_type}' not mapped. Available: {', '.join(ESPN_STAT_MAP.keys())}")
        return

    # Season format for CBB: season=2025 means 2024-25 season
    season = str(year)
    candidates = [
        f"https://site.api.espn.com/apis/common/v3/sports/basketball/mens-college-basketball/athletes/{athlete_id}/gamelog?season={season}",
        f"https://site.api.espn.com/apis/common/v3/sports/basketball/mens-college-basketball/athletes/{athlete_id}/gamelog",
    ]

    data = None
    for url in candidates:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('seasonTypes') or data.get('labels') or data.get('events'):
                    break
        except Exception:
            pass

    if not data:
        print("ESPN API returned no data for this player. Trying scrape fallback...")
        return None

    stats = _parse_espn_gamelog(data, espn_key)

    if stats is None:
        print("Could not parse ESPN gamelog data. Trying scrape fallback...")
        return None

    if not stats:
        print(f"No game-level stats found for {stat_type} on ESPN this season. Trying scrape fallback...")
        return None

    stats = stats[-num_games:]
    _print_results(player_name, stat_type, stats)
    return True


def _parse_espn_gamelog(data, espn_key):
    """Parse ESPN gamelog API response to extract a list of per-game values."""
    stats = []

    # Structure 1: seasonTypes -> categories -> events
    for season_type in data.get('seasonTypes', []):
        for cat in season_type.get('categories', []):
            if cat.get('name') == espn_key or cat.get('displayName', '').lower() == espn_key.lower():
                for ev in cat.get('events', []):
                    val = ev.get('value')
                    if val is not None:
                        try:
                            stats.append(int(float(val)))
                        except (ValueError, TypeError):
                            pass

    if stats:
        return stats

    # Structure 2: labels + statistics array
    labels = data.get('labels', [])
    if espn_key in labels:
        col_idx = labels.index(espn_key)
        for row in data.get('statistics', {}).get('rows', []):
            try:
                stats.append(int(float(row[col_idx])))
            except (IndexError, ValueError, TypeError):
                pass

    if stats:
        return stats

    # Structure 3: events list at top level
    for ev in data.get('events', []):
        if not isinstance(ev, dict):
            continue
        for stat in ev.get('statistics', []):
            if not isinstance(stat, dict):
                continue
            if stat.get('name') == espn_key:
                try:
                    stats.append(int(float(stat.get('value', 0))))
                except (ValueError, TypeError):
                    pass

    return stats if stats else None


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
# Scraping fallback path (Sports-Reference)
# ---------------------------------------------------------------------------

def _get_player_url_via_scraping(player_name, scraper):
    search_name = unidecode.unidecode(player_name).lower()
    search_url  = f"https://www.sports-reference.com/cbb/search/search.fcgi?search={search_name.replace(' ', '+')}"

    print(f"Searching Sports-Reference CBB for {player_name}...")
    try:
        resp = scraper.get(search_url, timeout=20)
        time.sleep(random.uniform(1, 3))

        if resp.status_code == 429:
            print("Rate limited — waiting 15s...")
            time.sleep(15)
            resp = scraper.get(search_url, timeout=20)
        if resp.status_code not in (200, 301, 302):
            print(f"Status {resp.status_code} from Sports-Reference.")
            return None

        if "/cbb/players" in resp.url and "/search/" not in resp.url:
            return resp.url

        soup  = BeautifulSoup(resp.content, 'html.parser')
        items = soup.find_all('div', class_='search-item')
        if items:
            link = items[0].find('a')
            if link and link.get('href'):
                href = link['href']
                base = 'https://www.sports-reference.com' if not href.startswith('http') else ''
                return base + href
        print(f"No results for '{player_name}' on Sports-Reference CBB.")
    except Exception as e:
        print(f"Connection error: {e}")
    return None


def _get_stats_via_scraping(player_name, stat_type, num_games, year):
    """Uses cloudscraper to bypass Cloudflare and scrape Sports-Reference CBB."""
    scraper    = make_scraper()
    player_url = _get_player_url_via_scraping(player_name, scraper)
    if not player_url:
        print("Could not locate player on Sports-Reference.")
        print("Tip: Try the player's full official name as listed on CBB Reference.")
        return

    # Build gamelog URL: strip .html and append /gamelog/{year}
    base = player_url.split('?')[0].rstrip('/')
    if base.endswith('.html'):
        base = base[:-5]
    gamelog_url = f"{base}/gamelog/{year}/"
    print(f"Fetching game log from: {gamelog_url}")

    resp = scraper.get(gamelog_url, timeout=20)
    time.sleep(random.uniform(2, 4))

    if resp.status_code != 200:
        resp = scraper.get(player_url, timeout=20)
        time.sleep(random.uniform(2, 4))
    if resp.status_code != 200:
        print(f"Failed to fetch page (Status: {resp.status_code})")
        return

    content = resp.content
    soup    = BeautifulSoup(content, 'html.parser')

    # Sports-Reference hides tables in HTML comments — extract them
    table_html = None
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        if 'id="gamelog"' in str(comment):
            table_html = str(comment)
            break
    if not table_html:
        div = soup.find('div', id='all_gamelog')
        if div:
            table_html = str(div)

    try:
        tables = pd.read_html(table_html or content)
    except ValueError:
        print("No tables found on page.")
        return

    df = next((t for t in tables if 'Date' in t.columns and 'Opp' in t.columns), None)
    if df is None:
        print("Could not identify a valid game log table.")
        return

    df = df[df['Date'] != 'Date'].dropna(subset=['Date'])

    if stat_type not in df.columns:
        print(f"Stat '{stat_type}' not found. Available: {', '.join(df.columns.tolist())}")
        return

    df[stat_type] = pd.to_numeric(df[stat_type], errors='coerce').fillna(0)
    stats = list(reversed(df.head(num_games)[stat_type].astype(int).tolist()))
    _print_results(player_name, stat_type, stats)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_cbb_player_stats(player_name, stat_type, num_games=30, year=2025):
    print(f"\n--- Fetching {stat_type} data for {player_name} (last {num_games} games of {year}) ---")
    print("Trying ESPN API first (no scraping required)...")
    result = _get_stats_via_espn(player_name, stat_type, num_games, year)
    if result is None:
        print("ESPN API did not return data — falling back to Sports-Reference scraping...")
        _get_stats_via_scraping(player_name, stat_type, num_games, year)


if __name__ == "__main__":
    print("CBB Player Stat Generator for Predictability API")
    print("-------------------------------------------------")
    print("Primary stats (ESPN API): PTS, REB, AST, STL, BLK, FGM, FGA, 3PM, 3PA, FTM, FTA, TO, MIN")
    print("Fallback stats (scraping): PTS, FGM, FGA, 3P, 3PA, FT, REB, AST, STL, BLK")

    while True:
        player_name = input("\nEnter College Basketball Player Name (or 'q' to quit): ").strip()
        if player_name.lower() == 'q':
            break
        stat_type = input("Enter Stat Type (e.g., PTS, AST, REB): ").strip().upper()
        try:
            year = int(input("Season end year (default 2025): ") or "2025")
        except ValueError:
            year = 2025
        try:
            num_games = int(input("Number of recent games to fetch (default 30): ") or "30")
        except ValueError:
            num_games = 30
        get_cbb_player_stats(player_name, stat_type, num_games, year)
        time.sleep(1)
