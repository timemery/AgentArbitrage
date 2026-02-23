
import os
import sqlite3
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env explicitly
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deals.db')

SELLER_ID = os.getenv("SP_API_SELLER_ID")
REFRESH_TOKEN = os.getenv("SP_API_REFRESH_TOKEN")

def inject_credentials():
    global SELLER_ID, REFRESH_TOKEN

    # Allow CLI args override
    if len(sys.argv) == 3:
        SELLER_ID = sys.argv[1]
        REFRESH_TOKEN = sys.argv[2]

    if not SELLER_ID:
        print("SP_API_SELLER_ID not in .env")
        # SELLER_ID = input("Enter Seller ID: ").strip() # Disabled for automation

    if not REFRESH_TOKEN:
        print("SP_API_REFRESH_TOKEN not in .env")
        # REFRESH_TOKEN = input("Enter Refresh Token: ").strip() # Disabled for automation

    if not SELLER_ID or not REFRESH_TOKEN:
        print("Error: Missing Credentials")
        return

    print(f"Injecting credentials for Seller ID: {SELLER_ID}")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Ensure table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_credentials (
                    user_id TEXT PRIMARY KEY,
                    refresh_token TEXT NOT NULL,
                    updated_at TIMESTAMP
                )
            """)

            updated_at = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
                INSERT OR REPLACE INTO user_credentials (user_id, refresh_token, updated_at)
                VALUES (?, ?, ?)
            """, (SELLER_ID, REFRESH_TOKEN, updated_at))

            conn.commit()
            print("Successfully injected credentials into deals.db")

    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    inject_credentials()
