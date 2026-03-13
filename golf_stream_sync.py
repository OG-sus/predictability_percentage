"""
golf_stream_sync.py — Live Golf Round Consistency Stream
Reads the "Golf" tab in your Google Sheet, fetches round scores,
and streams them to the overlay every 5 seconds.

Sheet columns used:
  A: Player name        E: Is_Live (TRUE/FALSE)   F: Featured (TRUE/FALSE)
  B: Score              K: Real_Data (chart line)  L: Target (avg)
  C: Avg                I: Featured_Title          J: Featured_Subtitle
  D: Stat type          (always "Rounds" for golf)
"""

import time
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from golf_gen import fetch_player_rounds_espn, synthetic_rounds
from fsr import calculate_predictability

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
SHEET_ID        = "1F3V-nmqchQE2-pauoRCVWDdZKLUIOLbSt1qeXvcUz6o"
SHEET_TAB_NAME  = "Golf"
CREDENTIALS_FILE = "service_account.json"
STREAM_DELAY    = 5   # seconds between each data push
K_FACTOR        = 2.0 # strict — golf rewards consistency

# Column indices (1-based for gspread update_cell)
COL_NAME         = 1
COL_SCORE        = 2
COL_AVG          = 3
COL_IS_LIVE      = 5
COL_FEATURED     = 6
COL_FEAT_TITLE   = 9
COL_FEAT_SUB     = 10
COL_REAL_DATA    = 11
COL_TARGET       = 12


def connect_to_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        print(f"⚠️  Tab '{SHEET_TAB_NAME}' not found. Create it in your Google Sheet first.")
        raise


def find_live_row(worksheet):
    """Return (row_index, row_data) for the first row where Is_Live = TRUE."""
    rows = worksheet.get_all_values()
    for i, row in enumerate(rows[1:], start=2):  # skip header
        if len(row) >= COL_IS_LIVE and str(row[COL_IS_LIVE - 1]).strip().upper() == 'TRUE':
            return i, row
    return None, None


def get_golf_rounds(player_name: str, num_rounds: int = 20) -> list[int]:
    """Try ESPN scrape first; fall back to synthetic rounds."""
    print(f"  Fetching rounds for {player_name}…")
    rounds = fetch_player_rounds_espn(player_name)
    if rounds and len(rounds) >= 4:
        print(f"  ✅ ESPN: {len(rounds)} rounds fetched.")
        return rounds[:num_rounds]
    print("  ESPN fetch failed — using synthetic rounds for stream.")
    avg = 72
    return synthetic_rounds(n=num_rounds, avg_score=avg, spread=4)


def stream_golf_data(worksheet, row_idx: int, player_name: str, rounds: list[int]):
    """Push rounds one at a time to the sheet, updating score each cycle."""
    print(f"\n▶  Streaming {len(rounds)} rounds for {player_name}…\n")

    cumulative: list[int] = []
    window_size = 10

    for i, round_score in enumerate(rounds):
        cumulative.append(round_score)
        window = cumulative[-window_size:]

        score = calculate_predictability(window, k=K_FACTOR)
        avg   = sum(cumulative) / len(cumulative)
        data_str = ', '.join(str(v) for v in cumulative)

        worksheet.update_cell(row_idx, COL_SCORE,     f'{score:.2f}')
        worksheet.update_cell(row_idx, COL_AVG,       f'{avg:.1f}')
        worksheet.update_cell(row_idx, COL_REAL_DATA, data_str)
        worksheet.update_cell(row_idx, COL_TARGET,    f'{avg:.1f}')
        worksheet.update_cell(row_idx, COL_FEAT_TITLE, player_name)
        worksheet.update_cell(row_idx, COL_FEAT_SUB,
                              f'Round {i+1}/{len(rounds)}  |  Avg: {avg:.1f}  |  FSR: {score:.1f}%')

        print(f"  Round {i+1:>2}: {round_score}  |  Avg: {avg:.1f}  |  Score: {score:.2f}%")
        time.sleep(STREAM_DELAY)

    # Hold the final state
    print(f"\n✅ Done streaming {player_name}. Holding final state. Press Ctrl+C to stop.")
    while True:
        time.sleep(30)


def main():
    print("=" * 50)
    print("  Golf Stream Sync  —  Predictability Score™")
    print(f"  Tab: {SHEET_TAB_NAME}  |  k={K_FACTOR}")
    print("=" * 50)

    worksheet = connect_to_sheet()
    row_idx, row_data = find_live_row(worksheet)

    if row_idx is None:
        print("❌  No row with Is_Live=TRUE found in the Golf tab.")
        print("    Set column E to TRUE for the player you want to stream.")
        return

    player_name = row_data[COL_NAME - 1].strip() if row_data else "Unknown Golfer"
    print(f"\n🏌️  Live player: {player_name}  (row {row_idx})\n")

    rounds = get_golf_rounds(player_name)

    try:
        stream_golf_data(worksheet, row_idx, player_name, rounds)
    except KeyboardInterrupt:
        print("\nStream stopped.")


if __name__ == "__main__":
    main()
