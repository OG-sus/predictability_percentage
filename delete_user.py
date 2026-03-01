import sqlite3
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Establishes a database connection."""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
        return sqlite3.connect(db_path)

def delete_user(username):
    """Deletes a user from the database by username."""
    if not username:
        print("Error: Please provide a username to delete.")
        return

    # Safety check: prevent accidental deletion of the admin account
    if username.lower() == 'ogz':
        print("Error: Cannot delete the primary admin account.")
        return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First, find the user to confirm existence
        find_query = "SELECT id FROM users WHERE username = %s" if DATABASE_URL else "SELECT id FROM users WHERE username = ?"
        cursor.execute(find_query, (username,))
        user = cursor.fetchone()

        if not user:
            print(f"User '{username}' not found.")
            return

        # If user exists, proceed with deletion
        delete_query = "DELETE FROM users WHERE username = %s" if DATABASE_URL else "DELETE FROM users WHERE username = ?"
        cursor.execute(delete_query, (username,))
        conn.commit()

        print(f"Successfully deleted user: '{username}'")

    except Exception as e:
        print(f"An error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Get username from command-line arguments
    if len(sys.argv) > 1:
        username_to_delete = sys.argv[1]
        delete_user(username_to_delete)
    else:
        print("Usage: python delete_user.py <username>")
