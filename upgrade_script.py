import sqlite3
import os

def set_user_pro(username):
    # Ensure we are looking in the correct directory
    db_path = os.path.join(os.getcwd(), 'database.db')
    
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Case-insensitive check just in case
        cursor.execute("UPDATE users SET tier = 'Pro' WHERE username = ?", (username,))
        if cursor.rowcount > 0:
            print(f"Success! User '{username}' is now set to 'Pro' tier.")
            conn.commit()
        else:
            print(f"User '{username}' not found.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    set_user_pro("ogz_local")
