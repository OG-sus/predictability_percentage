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
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
        return sqlite3.connect(db_path)

def list_users():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("--- Registered Users ---")
        print(f"{'ID':<4} {'Username':<20} {'Tier':<10} {'Stripe Customer ID':<30}")
        print("-" * 64)

        cursor.execute("SELECT id, username, tier, stripe_customer_id FROM users")
        users = cursor.fetchall()

        if not users:
            print("No users found in the database.")
        else:
            for user in users:
                user_id, username, tier, stripe_customer_id = user
                print(f"{user_id:<4} {username:<20} {tier:<10} {str(stripe_customer_id or 'N/A'):<30}")
    except Exception as e:
        print(f"Error accessing database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    list_users()
