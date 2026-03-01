import time
import os
import random
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
from fsr import calculate_predictability

# --- CONFIGURATION ---
SHEET_ID = "1F3V-nmqchQE2-pauoRCVWDdZKLUIOLbSt1qeXvcUz6o"
SHEET_TAB_NAME = "Sheet1"
CREDENTIALS_FILE = "service_account.json"

# Column Indices (1-based for gspread update_cell, or 0-based for row data)
# Name (1), Score (2), Avg (3), Type (4), Is_Live (5), Featured (6), 
# Top_Ticker (7), Bottom_Ticker (8), Featured_Title (9), Featured_Subtitle (10), 
# Real_Data (11 - K), Target (12 - L)

COL_IS_LIVE = 5
COL_FEATURED = 6
COL_FEATURED_TITLE = 9
COL_FEATURED_SUBTITLE = 10
COL_SCORE = 2
COL_REAL_DATA = 11
COL_TARGET = 12

def connect_to_sheet():
    """Connects to Google Sheets using the service account."""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    try:
        worksheet = sheet.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.sheet1
    return worksheet

def get_nba_stats(player_name, stat_type, num_games=50, retries=3, delay=5):
    """Fetches recent NBA stats for a player with retry logic."""
    nba_players = players.get_players()
    player_dict = [player for player in nba_players if player_name.lower() in player['full_name'].lower()]

    if not player_dict:
        print(f"Error: Player '{player_name}' not found.")
        return None

    player_id = player_dict[0]['id']
    
    for attempt in range(retries):
        try:
            current_season = "2025-26"
            gamelogs = playergamelog.PlayerGameLog(player_id=player_id, season=current_season).get_data_frames()[0]
            
            if len(gamelogs) < num_games:
                 previous_season = "2024-25"
                 gamelogs_prev = playergamelog.PlayerGameLog(player_id=player_id, season=previous_season).get_data_frames()[0]
                 gamelogs = pd.concat([gamelogs, gamelogs_prev])

            if stat_type.upper() not in gamelogs.columns:
                print(f"Error: Stat type '{stat_type}' not found.")
                return None

            stats = gamelogs.head(num_games)[stat_type.upper()].tolist()
            stats.reverse()
            return stats
        except Exception as e:
            print(f"Error fetching NBA stats on attempt {attempt + 1}/{retries}: {e}")
            if attempt < retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Failed to fetch NBA stats after multiple retries.")
                return None

def clean_sheet_for_live_player(worksheet, live_row_index, total_rows, player_name, stat_type):
    """
    Clears 'Is_Live', 'Featured', and AI columns for all non-live rows.
    Sets them for the live row.
    """
    print("Cleaning up sheet to ensure ONLY the selected player is live and featured...")
    
    # Prepare data for Columns E, F, I, J
    is_live_data = []
    featured_data = []
    title_data = []
    
    for i in range(2, total_rows + 1):
        if i == live_row_index:
            is_live_data.append(["TRUE"])
            featured_data.append(["TRUE"])
            title_data.append([player_name, f"Live {stat_type} Tracker"])
        else:
            is_live_data.append(["FALSE"])
            featured_data.append(["FALSE"])
            title_data.append(["", ""])
            
    try:
        # Batch update main columns
        worksheet.update(f'E2:E{total_rows}', is_live_data)
        worksheet.update(f'F2:F{total_rows}', featured_data)
        worksheet.update(f'I2:J{total_rows}', title_data)
        
        # Batch update to clear AI columns (M, N, P) to prevent overlay conflicts
        ai_cleanup_range = f'M2:P{total_rows}'
        ai_cleanup_data = [["", "", "", ""]] * (total_rows - 1)
        worksheet.update(ai_cleanup_range, ai_cleanup_data)
        
        print("Sheet cleanup complete. All other rows and AI data cleared.")
    except Exception as e:
        print(f"An error occurred during sheet cleanup: {e}")


def main():
    print("--- NBA Stream Sync Started ---")
    print("Restoring NBA live data to Google Sheets for Stream Overlay...")
    
    worksheet = connect_to_sheet()
    
    # 1. Identify which player/stat to stream
    all_rows = worksheet.get_all_values()
    
    live_row_index = -1
    for i, row in enumerate(all_rows[1:], start=2):
        # Find the FIRST row marked as 'Is_Live'
        is_live = row[4].upper() == 'TRUE' if len(row) > 4 else False
        if is_live:
            live_row_index = i
            player_name = row[0]
            stat_type = row[3]
            avg_target = float(row[2]) if row[2] else 0.0
            break
            
    if live_row_index == -1:
        print("No 'LIVE' row found. Please mark a row as TRUE in Column E.")
        return

    print(f"Streaming data for: {player_name} ({stat_type}) on row {live_row_index}")

    # CLEANUP: Ensure no other rows are marked as live/featured and clear AI columns
    clean_sheet_for_live_player(worksheet, live_row_index, len(all_rows), player_name, stat_type)

    # 2. Fetch initial historical data to seed the "live" feel
    historical_stats = get_nba_stats(player_name, stat_type)
    if not historical_stats:
        print("Failed to fetch historical stats.")
        return

    # To simulate "live" updates on the overlay, we'll iterate through the last few games
    # and update the sheet every few seconds.
    
    display_stats = historical_stats[-30:] # Last 30 games
    
    print(f"Starting live sync for {player_name}...")
    
    try:
        # We use enumerate to correctly handle repeated values in historical_stats
        for i, val in enumerate(display_stats):
            data_up_to_now = historical_stats[:len(historical_stats)-30+i+1]
            current_window = data_up_to_now[-20:] # Last 20 games
            score = calculate_predictability(current_window, k=0.5)
            
            # Create a string of all data points up to the current one for the graph
            real_data_string = ",".join(map(str, data_up_to_now))
            
            # Update Real Data (Column K) and Target (Column L)
            worksheet.update_cell(live_row_index, COL_REAL_DATA, real_data_string)
            worksheet.update_cell(live_row_index, COL_TARGET, avg_target)
            worksheet.update_cell(live_row_index, COL_SCORE, f"{score:.2f}")
            
            print(f"[{i+1}/{len(display_stats)}] Updated: Last Value={val} | Target={avg_target} | Score={score:.2f}")
            time.sleep(5) # Match the overlay's refresh rate (5s)
            
        print("\nFinished streaming real historical data.")
        print("The final, complete graph is now displayed on the overlay.")
        print("The script will now hold. Press Ctrl+C to exit.")
        
        # Keep the script alive to hold the final state, can be exited by user
        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        print("\nStream stopped by user.")

if __name__ == "__main__":
    main()
