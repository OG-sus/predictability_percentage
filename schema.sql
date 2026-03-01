DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS analyses;
DROP TABLE IF EXISTS folders;
DROP TABLE IF EXISTS users;

-- SQL for PostgreSQL (Supabase/DBeaver)
-- For PostgreSQL, use SERIAL for auto-incrementing IDs. 
-- If you already have tables, see instructions below to fix the 'id' column.

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'Free',
    stripe_customer_id TEXT,
    recovery_key_hash TEXT
);

CREATE TABLE folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    predictability_score TEXT NOT NULL,
    scores TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    folder_id INTEGER,
    k REAL DEFAULT 1.0,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (folder_id) REFERENCES folders (id)
);

CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    client_name TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
