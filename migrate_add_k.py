import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

# --- IMPORTANT ---
# This is a one-time use script to upgrade your database schema.
# After running it successfully, you should delete it.

def get_db_connection(database_url):
    if database_url:
        return psycopg2.connect(database_url, sslmode='require')
    else:
        return sqlite3.connect('database.db')

def upgrade_database():
    """
    Adds the 'k' column to the 'analyses' table to store the volatility constant.
    """
    load_dotenv()
    database_url = os.environ.get('DATABASE_URL')

    print("Connecting to the database...")
    conn = None
    try:
        conn = get_db_connection(database_url)
        cur = conn.cursor()

        print("Checking if 'k' column exists...")
        if database_url:
            # This query checks the database's catalog to see if the column is already there
            cur.execute("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='analyses' AND column_name='k';
            """)
            exists = cur.fetchone()
        else:
            cur.execute("PRAGMA table_info(analyses)")
            columns = [info[1] for info in cur.fetchall()]
            exists = 'k' in columns
        
        if exists:
            print("'k' column already exists. No changes needed.")
        else:
            print("Adding 'k' column to 'analyses' table with a default value of 1.0...")
            # REAL is the correct type for a floating point number
            cur.execute("ALTER TABLE analyses ADD COLUMN k REAL DEFAULT 1.0;")
            conn.commit()
            print("SUCCESS: The 'k' column was added successfully.")

    except Exception as e:
        print("\n--- AN ERROR OCCURRED ---")
        print(f"Error details: {e}")
        print("The database was not changed.")
        if conn:
            conn.rollback() # Roll back any partial changes
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    upgrade_database()
