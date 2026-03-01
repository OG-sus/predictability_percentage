import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# The user mentioned they moved to Supabase and use DBeaver.
# Since I don't have their current DATABASE_URL in .env (it's commented out or missing),
# I'll create this script for THEM to run or for me to use if they provide the URL.

def check_postgres_schema():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not found in environment.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        print("Checking 'users' table schema in PostgreSQL...")
        
        # Check column defaults and types
        cur.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'id';
        """)
        row = cur.fetchone()
        if row:
            print(f"Column: {row[0]}")
            print(f"Type: {row[1]}")
            print(f"Default: {row[2]}")
            print(f"Nullable: {row[3]}")
            
            if row[2] and 'nextval' in row[2]:
                print("SUCCESS: ID column has a sequence (auto-increment).")
            else:
                print("WARNING: ID column does NOT have a sequence. This is why registration fails.")
        else:
            print("ERROR: 'users' table not found.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    check_postgres_schema()
