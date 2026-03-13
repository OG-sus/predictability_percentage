"""One-off migration: adds public_token column to analyses table."""
import os
import sqlite3

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS public_token TEXT UNIQUE;")
    conn.commit()
    cur.close()
    conn.close()
    print("✅ PostgreSQL: public_token column added.")
else:
    conn = sqlite3.connect('database.db')
    try:
        conn.execute("ALTER TABLE analyses ADD COLUMN public_token TEXT;")
        conn.commit()
        print("✅ SQLite: public_token column added.")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("ℹ️  Column already exists, skipping.")
        else:
            raise
    finally:
        conn.close()
