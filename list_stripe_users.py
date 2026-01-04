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

def list_stripe_users():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, username, tier, stripe_customer_id FROM users WHERE stripe_customer_id IS NOT NULL AND stripe_customer_id != ''")
        users = cursor.fetchall()
        
        if users:
            print(f"{'ID':<5} {'Username':<20} {'Tier':<15} {'Stripe Customer ID'}")
            print("-" * 60)
            for user in users:
                print(f"{user[0]:<5} {user[1]:<20} {user[2]:<15} {user[3]}")
        else:
            print("No users found with a Stripe Customer ID.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    list_stripe_users()
