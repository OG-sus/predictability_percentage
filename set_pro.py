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

def set_user_pro(username):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if DATABASE_URL else '?'
        
        # Check if user exists
        cursor.execute(f"SELECT id FROM users WHERE username = {placeholder}", (username,))
        user = cursor.fetchone()
        
        if not user:
            print(f"Error: User '{username}' not found.")
            return

        # Update to Pro
        cursor.execute(f"UPDATE users SET tier = 'Pro' WHERE username = {placeholder}", (username,))
        conn.commit()
        print(f"Success! User '{username}' is now set to 'Pro' tier.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    username = input("Enter the username to upgrade to Pro: ")
    set_user_pro(username)
