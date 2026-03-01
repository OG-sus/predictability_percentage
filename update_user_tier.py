import sqlite3
import psycopg2
import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        return sqlite3.connect('database.db')

def update_user_to_pro(username_to_update):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if DATABASE_URL else '?'

        # Check if user exists first
        cursor.execute(f"SELECT id FROM users WHERE username = {placeholder}", (username_to_update,))
        user = cursor.fetchone()
        
        if user:
            cursor.execute(f"UPDATE users SET tier = 'Pro' WHERE username = {placeholder}", (username_to_update,))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"✅ Success: User '{username_to_update}' has been upgraded to 'Pro' tier.")
            else:
                print(f"⚠️ Warning: User '{username_to_update}' found but update affected 0 rows.")
        else:
            print(f"❌ Error: User '{username_to_update}' not found in database.")
            
    except Exception as e:
        print(f"🚨 An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upgrade a user to Pro tier.')
    parser.add_argument('username', nargs='?', help='The username to upgrade')
    
    args = parser.parse_args()
    
    if args.username:
        update_user_to_pro(args.username)
    else:
        print("Usage: python update_user_tier.py <username>")
        print("Example: python update_user_tier.py user1")
