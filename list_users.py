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
        print(f"{'ID':<4} {'Username':<20} {'Tier':<10} {'Created At':<25} {'Stripe Customer ID':<30}")
        print("-" * 90)

        # Try to select with created_at first
        try:
            cursor.execute("SELECT id, username, tier, created_at, stripe_customer_id FROM users ORDER BY id DESC")
            users = cursor.fetchall()
        except Exception:
            # Fallback for databases without created_at column
            if conn: conn.rollback()
            cursor.execute("SELECT id, username, tier, stripe_customer_id FROM users ORDER BY id DESC")
            users = []
            for row in cursor.fetchall():
                # Add 'N/A' for created_at
                users.append((row[0], row[1], row[2], 'N/A', row[3]))

        if not users:
            print("No users found in the database.")
        else:
            for user in users:
                user_id, username, tier, created_at, stripe_customer_id = user
                
                # Safe string conversion
                s_id = str(user_id)
                s_username = str(username)
                s_tier = str(tier)
                s_created = str(created_at) if created_at else 'N/A'
                s_stripe = str(stripe_customer_id) if stripe_customer_id else 'N/A'

                print(f"{s_id:<4} {s_username:<20} {s_tier:<10} {s_created:<25} {s_stripe:<30}")
    except Exception as e:
        print(f"Error accessing database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    list_users()
