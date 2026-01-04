import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        return sqlite3.connect('database.db')

def migrate_database():
    print("Checking database schema...")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if stripe_customer_id column exists
        exists = False
        if DATABASE_URL:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='stripe_customer_id';")
            exists = cursor.fetchone() is not None
        else:
            cursor.execute("PRAGMA table_info(users)")
            columns = [info[1] for info in cursor.fetchall()]
            exists = 'stripe_customer_id' in columns
        
        if not exists:
            print("Adding 'stripe_customer_id' column to 'users' table...")
            cursor.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
            conn.commit()
            print("Column added successfully.")
        else:
            print("'stripe_customer_id' column already exists.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database()
