#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Initialize migrations folder if it doesn't exist
if [ ! -d "migrations" ]; then
    echo "Initializing migrations..."
    flask db init
    flask db migrate -m "Initial migration"
fi

# Run database migrations
echo "Running migrations..."
flask db upgrade

# Run manual fix for recovery column (Safe to run multiple times)
echo "Ensuring recovery column exists..."
python add_recovery_column.py

# Ensure leads table exists (Safe to run multiple times)
echo "Ensuring leads table exists..."
python migrate_add_leads.py

# Ensure public_token column exists on analyses (Safe to run multiple times)
echo "Ensuring public_token column exists..."
python migrate_add_public_token.py

