"""
Migration: Add leads table
Run once: python migrate_add_leads.py
"""
import os
import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

SQL_PG = """
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT,
    industry TEXT,
    company_size TEXT,
    use_case TEXT,
    message TEXT,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'new'
);
"""

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT,
    industry TEXT,
    company_size TEXT,
    use_case TEXT,
    message TEXT,
    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'new'
);
"""

if DATABASE_URL:
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url, sslmode='require')
    cur = conn.cursor()
    cur.execute(SQL_PG)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ leads table created in PostgreSQL.")
else:
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
    conn = sqlite3.connect(db_path)
    conn.execute(SQL_SQLITE)
    conn.commit()
    conn.close()
    print("✅ leads table created in SQLite.")
