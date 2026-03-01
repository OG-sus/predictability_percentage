import os
import psycopg2
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        # Connect to local SQLite database
        return sqlite3.connect('database.db')

def add_recovery_column():
    """
    Adds the 'recovery_key_hash' column to the 'users' table for both
    PostgreSQL and SQLite, if it doesn't already exist.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if DATABASE_URL:
            # PostgreSQL: Check if column exists
            cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='recovery_key_hash';")
            exists = cur.fetchone()
            if not exists:
                print("PostgreSQL: Adding 'recovery_key_hash' column to 'users' table...")
                cur.execute("ALTER TABLE users ADD COLUMN recovery_key_hash VARCHAR(255);")
                conn.commit()
                print("Success: Column added to PostgreSQL.")
            else:
                print("Notice: 'recovery_key_hash' column already exists in PostgreSQL.")
        else:
            # SQLite: Check if column exists
            cur.execute("PRAGMA table_info(users)")
            columns = [info[1] for info in cur.fetchall()]
            if 'recovery_key_hash' not in columns:
                print("SQLite: Adding 'recovery_key_hash' column to 'users' table...")
                cur.execute("ALTER TABLE users ADD COLUMN recovery_key_hash TEXT;")
                conn.commit()
                print("Success: Column added to SQLite.")
            else:
                print("Notice: 'recovery_key_hash' column already exists in SQLite.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_recovery_column()
