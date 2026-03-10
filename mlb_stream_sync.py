"""
mlb_stream_sync.py — MLB Stream Sync
======================================
Mirrors nba_stream_sync.py for MLB data via pybaseball (Statcast).

Setup:
  1. In your Google Sheet, add a tab named "MLB"
  2. Copy the same column structure from your NBA sheet (A-L)
  3. Fill in player rows; set Is_Live=TRUE for the player to feature
  4. Run: python mlb_stream_sync.py

Notes:
  - MLB season runs April–October. Use year=2025 for last season's data
    until Opening Day (April 1, 2026).
  - Available stats: H (hits), HR (home runs), SO/K (strikeouts), BB (walks)
  - Requires: pip install pybaseball
"""

import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from mlb_data_gen import get_mlb_stats_raw
from fsr import calculate_predictability

# --- CONFIGURATION ---
SHEET_ID        = "1F3V-nmqchQE2-pauoRCVWDdZKLUIOLbSt1qeXvcUz6o"  # Same sheet as NBA
SHEET_TAB_NAME  = "MLB"
CREDENTIALS_FILE = "service_account.json"
K_FACTOR        = 0.5   # Sports — forgiving
REFRESH_SECONDS = 5
DEFAULT_NUM_GAMES = 30
DEFAULT_YEAR    = 2025  # Update to 2026 after Opening Day (April 1, 2026)

# Column indices (match NBA sheet layout)
COL_NAME       = 1
COL_SCORE      = 2
COL_AVG        = 3
COL_TYPE       = 4
COL_IS_LIVE    = 5
COL_FEATURED   = 6
COL_TITLE      = 9
COL_SUBTITLE   = 10
COL_REAL_DATA  = 11
COL_TARGET     = 12


def connect_to_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        raise RuntimeError(f"Tab '{SHEET_TAB_NAME}' not found. Add it to your Google Sheet first.")


def clean_sheet(worksheet, live_row, total_rows, player_name, stat_type):
    print(f"Setting up sheet: '{player_name} ({stat_type})' → row {live_row}")
    is_live_col, featured_col, title_col = [], [], []

    for i in range(2, total_rows + 1):
        if i == live_row:
            is_live_col.append(["TRUE"])
            featured_col.append(["TRUE"])
            title_col.append([player_name, f"Live {stat_type} Tracker"])
        else:
            is_live_col.append(["FALSE"])
            featured_col.append(["FALSE"])
            title_col.append(["", ""])

    worksheet.update(f'E2:E{total_rows}', is_live_col)
    worksheet.update(f'F2:F{total_rows}', featured_col)
    worksheet.update(f'I2:J{total_rows}', title_col)
    worksheet.update(f'M2:P{total_rows}', [["", "", "", ""]] * (total_rows - 1))
    print("Sheet ready.")


def main():
    print("--- MLB Stream Sync Started ---")
    worksheet = connect_to_sheet()

    all_rows = worksheet.get_all_values()
    live_row, player_name, stat_type, avg_target, year = -1, None, 'H', 0.0, DEFAULT_YEAR

    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) > 4 and row[COL_IS_LIVE - 1].upper() == 'TRUE':
            live_row    = i
            player_name = row[COL_NAME - 1].strip()
            stat_type   = row[COL_TYPE - 1].strip().upper() or 'H'
            avg_target  = float(row[COL_AVG - 1]) if row[COL_AVG - 1] else 0.0
            break

    if live_row == -1:
        print("No Is_Live=TRUE row found. Mark a player row in column E.")
        return

    print(f"Streaming: {player_name} — {stat_type} ({DEFAULT_YEAR} season)")

    stats = get_mlb_stats_raw(player_name, stat_type, num_games=DEFAULT_NUM_GAMES, year=year)
    if not stats:
        print(f"Could not fetch stats for '{player_name}'. Ensure pybaseball is installed")
        print("and the player name matches exactly (e.g., 'Aaron Judge', 'Shohei Ohtani').")
        return

    if not avg_target:
        avg_target = round(sum(stats) / len(stats), 2)
        worksheet.update_cell(live_row, COL_AVG, avg_target)

    clean_sheet(worksheet, live_row, len(all_rows), player_name, stat_type)

    print(f"Streaming {len(stats)} games for {player_name}...")
    try:
        for i, val in enumerate(stats):
            window = stats[max(0, i - 19): i + 1]
            score  = calculate_predictability(window, k=K_FACTOR)
            real_data_str = ",".join(map(str, stats[:i + 1]))

            worksheet.update_cell(live_row, COL_REAL_DATA, real_data_str)
            worksheet.update_cell(live_row, COL_TARGET, avg_target)
            worksheet.update_cell(live_row, COL_SCORE, f"{score:.2f}")

            print(f"  [{i+1}/{len(stats)}] {stat_type}={val} | Avg={avg_target} | Score={score:.2f}")
            time.sleep(REFRESH_SECONDS)

        print("\nDone streaming. Holding final state. Press Ctrl+C to exit.")
        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        print("\nStream stopped.")


if __name__ == "__main__":
    main()
