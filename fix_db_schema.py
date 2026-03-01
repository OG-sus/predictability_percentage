import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def fix_schema():
    if not DATABASE_URL:
        print("Error: DATABASE_URL is not set in .env")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        
        print("Connected to database...")

        # 1. Check the current type of user_id in analyses
        print("Checking 'analyses' table schema...")
        cur.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'analyses' AND column_name = 'user_id';
        """)
        result = cur.fetchone()
        if result:
            print(f"Current 'user_id' type: {result[0]}")
        
        # 2. Attempt to convert it back to INTEGER
        # We use 'USING user_id::integer' to try and convert existing data.
        # If there is garbage data (actual UUIDs) in there, this might fail, 
        # in which case we might need to clear the column or table.
        print("Attempting to revert 'user_id' to INTEGER...")
        
        try:
            cur.execute("""
                ALTER TABLE analyses 
                ALTER COLUMN user_id TYPE INTEGER 
                USING user_id::integer;
            """)
            conn.commit()
            print("Success! 'user_id' is now an INTEGER.")
        except Exception as e:
            print(f"Could not convert directly: {e}")
            print("Rolling back and trying a harder reset (Drop/Add column)...")
            conn.rollback()
            
            # Option B: If conversion fails, we might have to drop the column or delete bad rows.
            # Let's try deleting rows that aren't integers first? No, simpler to just reset the column if it fails.
            # WARNING: This deletes the user association for existing analyses if they are UUIDs.
            
            confirm = input("Direct conversion failed. Do you want to DROP the user_id column and recreate it? This will lose user associations for existing analyses. (y/n): ")
            if confirm.lower() == 'y':
                cur.execute("ALTER TABLE analyses DROP COLUMN user_id;")
                cur.execute("ALTER TABLE analyses ADD COLUMN user_id INTEGER;")
                # We should probably add the Foreign Key constraint back too
                cur.execute("ALTER TABLE analyses ADD CONSTRAINT analyses_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);")
                conn.commit()
                print("Column recreated as INTEGER.")
            else:
                print("Operation cancelled.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    fix_schema()
