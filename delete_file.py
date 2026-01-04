import os
try:
    if os.path.exists("nba_data.py"):
        os.remove("nba_data.py")
        print("nba_data.py deleted")
    else:
        print("nba_data.py not found")
except Exception as e:
    print(f"Error: {e}")
