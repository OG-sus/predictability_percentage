import os
import sys
import psycopg2
import uuid
from werkzeug.security import generate_password_hash
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def create_api_user(username):
    """
    Creates a new user, sets their tier to API_Business, and generates an API key.
    Uses psycopg2 which is already in requirements.txt.
    """
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in .env file.")
        return

    # Default password for new API users
    temp_password = "password123"
    password_hash = generate_password_hash(temp_password)
    
    conn = None
    try:
        print(f"Connecting to database...")
        
        # Connect using psycopg2 (standard for this project)
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        print("Connection successful.")

        # 1. Create the user
        print(f"Creating user '{username}' with tier 'API_Business'...")
        
        # Check if user exists first
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()
        
        if existing_user:
            print(f"User '{username}' already exists. Updating tier to API_Business...")
            user_id = existing_user[0]
            cur.execute("UPDATE users SET tier = 'API_Business' WHERE id = %s", (user_id,))
        else:
            # Create new user
            recovery_key = str(uuid.uuid4())
            recovery_key_hash = generate_password_hash(recovery_key)
            
            cur.execute(
                "INSERT INTO users (username, password, tier, recovery_key_hash) VALUES (%s, %s, 'API_Business', %s) RETURNING id;",
                (username, password_hash, recovery_key_hash)
            )
            user_id = cur.fetchone()[0]
            print(f"Successfully created user with ID: {user_id}")
            print(f"Recovery Key: {recovery_key}")

        # 2. Generate an API key for the user
        print("Generating API key...")
        api_key = str(uuid.uuid4())
        client_name = f"{username}'s Key"
        
        # Deactivate old keys if any
        cur.execute("UPDATE api_keys SET is_active = false WHERE user_id = %s", (user_id,))
        
        # Insert new key
        cur.execute(
            "INSERT INTO api_keys (user_id, api_key, client_name, is_active) VALUES (%s, %s, %s, true);",
            (user_id, api_key, client_name)
        )
        print("Successfully created API key.")

        conn.commit()

        # 3. Print the results
        print("\n--- API User Created/Updated Successfully ---")
        print(f"Username: {username}")
        print(f"Password: {temp_password}")
        print(f"API Key: {api_key}")
        print("---------------------------------------------")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_api_user.py <username>")
        sys.exit(1)
    
    target_username = sys.argv[1]
    create_api_user(target_username)
