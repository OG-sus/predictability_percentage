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
    print("Starting safe migration for Folders feature...")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1. Create the 'folders' table
        print("Creating 'folders' table if not exists...")
        if DATABASE_URL:
            # PostgreSQL syntax
            cur.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        else:
            # SQLite syntax
            cur.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        
        # 2. Add 'folder_id' column to 'analyses' table
        print("Checking 'analyses' table for 'folder_id' column...")
        
        # Check if column exists
        if DATABASE_URL:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='analyses' AND column_name='folder_id';")
        else:
            # SQLite check is a bit different, usually involves PRAGMA
            # For simplicity in this script, we'll try to add it and catch the error if it exists
            pass 

        # Attempt to add the column. If it fails, it likely already exists.
        try:
            if DATABASE_URL:
                if not cur.fetchone():
                    print("Adding 'folder_id' to PostgreSQL 'analyses' table...")
                    cur.execute("ALTER TABLE analyses ADD COLUMN folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL;")
            else:
                print("Adding 'folder_id' to SQLite 'analyses' table...")
                cur.execute("ALTER TABLE analyses ADD COLUMN folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL;")
        except Exception as e:
            print(f"Column 'folder_id' might already exist or error: {e}")
            conn.rollback() # Rollback this specific step if it failed, but continue
        else:
            conn.commit() # Commit if successful

        print("Migration completed successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
