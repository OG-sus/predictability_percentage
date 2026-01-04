import sqlite3
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        return sqlite3.connect('database.db')

def update_user_tier(username, tier):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if DATABASE_URL else '?'

        cursor.execute(f"UPDATE users SET tier = {placeholder} WHERE username = {placeholder}", (tier, username))
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"SUCCESS: User '{username}' has been updated to tier '{tier}'.")
        else:
            print(f"ERROR: User '{username}' not found.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python update_user_tier.py <username> <tier>")
        print("Example: python update_user_tier.py OGZ API_Business")
    else:
        target_user = sys.argv[1]
        target_tier = sys.argv[2]
        update_user_tier(target_user, target_tier)
