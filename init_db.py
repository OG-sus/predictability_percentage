import sqlite3
import os
import psycopg2
from dotenv import load_dotenv

# Explicitly load the .env file from the current directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    print(f"Loading .env file from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print("Warning: .env file not found.")

def init_db():
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        print("Connecting to PostgreSQL...")
        conn = psycopg2.connect(database_url, sslmode='require')
    else:
        print("Connecting to SQLite...")
        conn = sqlite3.connect('database.db')

    with open('schema.sql') as f:
        schema = f.read()

    cursor = conn.cursor()

    # Split schema into individual statements
    statements = schema.split(';')

    try:
        for statement in statements:
            if statement.strip():
                cursor.execute(statement)
        conn.commit()
        print("Database has been initialized successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    init_db()
