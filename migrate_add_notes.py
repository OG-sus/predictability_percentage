import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        return sqlite3.connect(LOCAL_DB)

def migrate():
    print("Starting migration: Adding 'notes' column to 'analyses' table...")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check if column exists
        if DATABASE_URL:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='analyses' AND column_name='notes';")
        else:
            # SQLite check
            cur.execute("PRAGMA table_info(analyses)")
            columns = [info[1] for info in cur.fetchall()]
            if 'notes' in columns:
                print("'notes' column already exists in SQLite.")
                return

        # Attempt to add the column
        if DATABASE_URL:
            if not cur.fetchone():
                print("Adding 'notes' to PostgreSQL 'analyses' table...")
                cur.execute("ALTER TABLE analyses ADD COLUMN notes TEXT;")
            else:
                print("'notes' column already exists in PostgreSQL.")
        else:
            print("Adding 'notes' to SQLite 'analyses' table...")
            cur.execute("ALTER TABLE analyses ADD COLUMN notes TEXT;")
        
        conn.commit()
        print("Migration completed successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
