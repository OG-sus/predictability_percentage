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

def update_user_to_pro(username_to_update):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if DATABASE_URL else '?'

        cursor.execute(f"UPDATE users SET tier = 'Pro' WHERE username = {placeholder}", (username_to_update,))
        conn.commit()
        if cursor.rowcount > 0:
            print(f"User '{username_to_update}' has been successfully updated to 'Pro' tier.")
        else:
            print(f"User '{username_to_update}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # IMPORTANT: Replace 'user1' with the actual username you want to make Pro
    update_user_to_pro('user1')
