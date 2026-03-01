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

def create_api_key(username, api_key):
    """
    Manually creates an API key for a given user.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if DATABASE_URL else '?'

        # 1. Find the user's ID
        cursor.execute(f"SELECT id FROM users WHERE username = {placeholder}", (username,))
        user_row = cursor.fetchone()
        
        if not user_row:
            print(f"Error: User '{username}' not found in the 'users' table.")
            return

        # Handle row indexing based on cursor type
        if DATABASE_URL:
            # Psycopg2 with default cursor returns tuples by default unless specified
            user_id = user_row[0]
        else:
            user_id = user_row[0]

        # 2. Insert the new API key
        # For client_name, we'll just use the username for now.
        cursor.execute(f"""
            INSERT INTO api_keys (user_id, api_key, client_name, is_active, usage_count)
            VALUES ({placeholder}, {placeholder}, {placeholder}, 1, 0)
        """, (user_id, api_key, username))
        
        conn.commit()
        print(f"✅ Success! API key created for user '{username}' (ID: {user_id}).")

    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"Error: This API key or a key for this user may already exist.")
        else:
            print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_api_key.py <username> <api_key>")
        sys.exit(1)
    
    username_to_create = sys.argv[1]
    key_to_create = sys.argv[2]
    create_api_key(username_to_create, key_to_create)
