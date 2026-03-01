"""
NBA Player Stability Analysis (2024-25 Season)
----------------------------------------------
This script generates a dataset quantifying the consistency of top NBA players
using the Predictability Score™ (FSR) algorithm.

It fetches real-time game logs via the `nba_api`, calculates stability scores
based on a Coefficient of Variation with exponential decay, and exports the
results to CSV for further analysis.

Metrics:
- Predictability Score (0-100%): Higher is more consistent.
- Stability Rating: Elite, High, Medium, Low, Volatile.

Requirements:
- nba_api
- pandas
- fsr (Internal Engine)

Author: FSR_c_% Team
"""

import pandas as pd
import time
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
from fsr import calculate_predictability

# List of top players to analyze
TARGET_PLAYERS = [
    "LeBron James", "Stephen Curry", "Nikola Jokic", "Luka Doncic", 
    "Giannis Antetokounmpo", "Jayson Tatum", "Joel Embiid", "Kevin Durant",
    "Devin Booker", "Anthony Edwards", "Shai Gilgeous-Alexander",
    "Tyrese Haliburton", "Donovan Mitchell", "Kawhi Leonard", "Anthony Davis",
    "Damian Lillard", "Trae Young", "De'Aaron Fox", "Jimmy Butler",
    "Bam Adebayo", "Domantas Sabonis", "Kyrie Irving", "Zion Williamson",
    "Ja Morant", "Victor Wembanyama", "Paolo Banchero", "Chet Holmgren"
]

STATS_TO_TRACK = ['PTS', 'AST', 'REB']

def get_stability_rating(score):
    if score >= 85: return "Elite"
    if score >= 75: return "High"
    if score >= 60: return "Medium"
    if score >= 40: return "Low"
    return "Volatile"

def generate_dataset():
    all_data = []
    
    print(f"Starting analysis for {len(TARGET_PLAYERS)} players...")
    print("Fetching data from NBA API...")
    
    nba_players = players.get_players()
    
    for player_name in TARGET_PLAYERS:
        # Find player ID
        player_dict = [p for p in nba_players if p['full_name'].lower() == player_name.lower()]
        if not player_dict:
            # Try partial match
            player_dict = [p for p in nba_players if player_name.lower() in p['full_name'].lower()]
            
        if not player_dict:
            print(f"Could not find {player_name}")
            continue
            
        player_id = player_dict[0]['id']
        print(f"Processing {player_name}...")
        
        try:
            # Fetch last 30 games
            gamelog = playergamelog.PlayerGameLog(player_id=player_id, season='2024-25') 
            df = gamelog.get_data_frames()[0]
            
            if len(df) < 5:
                print(f"  Not enough games for {player_name}")
                continue
                
            recent_games = df.head(30) # Last 30 games
            
            for stat in STATS_TO_TRACK:
                values = recent_games[stat].tolist()
                # Reverse to chronological order (oldest to newest)
                values.reverse() 
                
                if not values: continue
                
                # Calculate Metrics
                avg = sum(values) / len(values)
                # k=0.5 is the tuned parameter for Sports (forgiving of occasional bad games)
                score = calculate_predictability(values, k=0.5) 
                
                all_data.append({
                    "Player": player_name,
                    "Stat_Type": stat,
                    "Games_Analyzed": len(values),
                    "Average_Value": round(avg, 2),
                    "Predictability_Score": round(score, 2),
                    "Stability_Rating": get_stability_rating(score),
                    "Last_5_Values": str(values[-5:]),
                    "Data_Source": "Predictability API Engine"
                })
                
            time.sleep(0.6) # Rate limit politeness
            
        except Exception as e:
            print(f"  Error processing {player_name}: {e}")
            
    # Save to CSV
    output_df = pd.DataFrame(all_data)
    filename = "nba_player_stability_metrics_2026.csv"
    output_df.to_csv(filename, index=False)
    print(f"\nSuccess! Dataset saved to {filename}")
    print("-" * 30)
    print(output_df[['Player', 'Stat_Type', 'Predictability_Score', 'Stability_Rating']].head(10))

if __name__ == "__main__":
    generate_dataset()
