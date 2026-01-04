import csv
import json
from collections import defaultdict

def create_data_json_from_csv(input_csv_path, output_json_path='data.json'):
    """
    Reads a CSV file containing game-by-game fantasy points and converts it
    into the JSON format used by the FSR web application.

    Args:
        input_csv_path (str): The path to the input CSV file.
        output_json_path (str): The path where the output data.json will be saved.

    Expected CSV Format:
    The CSV file must contain at least two columns. The script is pre-configured
    to look for headers named 'player_name' and 'fantasy_points'. If your file
    uses different names, you will need to update the 'PLAYER_NAME_COLUMN' and
    'FANTASY_POINTS_COLUMN' variables inside this function.
    """
    
    # --- CONFIGURATION ---
    # Adjust these column names to match the headers in your CSV file.
    PLAYER_NAME_COLUMN = 'player_name'
    FANTASY_POINTS_COLUMN = 'fantasy_points'
    # -------------------

    player_scores = defaultdict(list)

    print(f"Reading data from '{input_csv_path}'...")

    try:
        with open(input_csv_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            for row in reader:
                player_name = row.get(PLAYER_NAME_COLUMN)
                try:
                    fantasy_points = float(row.get(FANTASY_POINTS_COLUMN, 0))
                    if player_name:
                        player_scores[player_name].append(fantasy_points)
                except (ValueError, TypeError):
                    # Skip rows where fantasy_points is not a valid number
                    continue

        if not player_scores:
            print("Warning: No data was processed. Check the CSV file and column name configuration.")
            return

        # Structure the data in the final format for the application
        output_data = {
            'players': {name: {'scores': scores} for name, scores in player_scores.items()}
        }

        with open(output_json_path, 'w') as outfile:
            json.dump(output_data, outfile, indent=2)

        print(f"Successfully created '{output_json_path}' with data for {len(player_scores)} players.")

    except FileNotFoundError:
        print(f"Error: The file '{input_csv_path}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    # --- HOW TO USE ---
    # 1. Find and download a CSV file with NBA player game data.
    #    A good place to look is Kaggle.com.
    #
    # 2. Place the CSV file in your project directory.
    #    For this example, let's assume you downloaded a file named 'nba_game_data.csv'.
    #
    # 3. Update the 'input_file_path' variable below to match your file's name.
    #
    # 4. If needed, change the column name variables inside the function above.
    #
    # 5. Run this script once from your terminal:
    #    python process_data.py

    input_file_path = 'nba_game_data.csv'  # <-- IMPORTANT: Change this to your file's name
    
    create_data_json_from_csv(input_file_path)
