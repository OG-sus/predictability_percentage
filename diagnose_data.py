import os
import sqlite3
import psycopg2
import json
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        return sqlite3.connect(LOCAL_DB)

def diagnose():
    print("Starting database diagnosis...")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Fetch all analyses
        if DATABASE_URL:
            cur.execute("SELECT id, name, scores FROM analyses;")
        else:
            cur.execute("SELECT id, name, scores FROM analyses;")
        
        rows = cur.fetchall()
        print(f"Found {len(rows)} analyses. Checking for corruption...")

        corrupted_ids = []
        
        for row in rows:
            # Handle row access based on DB type (tuple vs dict-like)
            analysis_id = row[0]
            name = row[1]
            scores_raw = row[2]

            try:
                # Try to parse the JSON
                if isinstance(scores_raw, str):
                    json.loads(scores_raw)
                # If it's already a list/dict (some drivers do this automatically), it's fine
                elif isinstance(scores_raw, (list, dict)):
                    pass
                else:
                    print(f"Warning: ID {analysis_id} ('{name}') has unexpected type: {type(scores_raw)}")

            except json.JSONDecodeError as e:
                print(f"CORRUPTION DETECTED: ID {analysis_id} ('{name}')")
                print(f"  Error: {e}")
                print(f"  Raw Data: {scores_raw}")
                corrupted_ids.append(analysis_id)
            except Exception as e:
                print(f"Unknown error for ID {analysis_id} ('{name}'): {e}")
                corrupted_ids.append(analysis_id)

        if corrupted_ids:
            print("\n--- DIAGNOSIS REPORT ---")
            print(f"Found {len(corrupted_ids)} corrupted records.")
            print(f"Corrupted IDs: {corrupted_ids}")
            print("To fix, you can run a DELETE command for these specific IDs.")
        else:
            print("\n--- DIAGNOSIS REPORT ---")
            print("No JSON corruption found. All 'scores' fields are valid.")

    except Exception as e:
        print(f"Script failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    diagnose()
