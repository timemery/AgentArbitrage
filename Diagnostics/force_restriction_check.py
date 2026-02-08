
import sqlite3
import os
import sys
from datetime import datetime

# Try to find the database path
DB_PATH = os.getenv('DATABASE_URL', os.path.join(os.getcwd(), 'deals.db'))
if not os.path.exists(DB_PATH):
    # Try parent directory if running from Diagnostics/
    DB_PATH = os.path.join(os.path.dirname(os.getcwd()), 'deals.db')
    if not os.path.exists(DB_PATH):
        # Try explicit relative path if we are in root
        DB_PATH = 'deals.db'

print(f"Using Database: {DB_PATH}")

if not os.path.exists(DB_PATH):
    print("Error: Database file not found!")
    sys.exit(1)

# Ensure we can import the celery app
sys.path.append(os.getcwd())
try:
    from worker import celery_app
except ImportError:
    # Try parent dir
    sys.path.append(os.path.dirname(os.getcwd()))
    try:
        from worker import celery_app
    except ImportError:
        print("Error: Could not import celery_app. Please run from the project root.")
        sys.exit(1)

def force_check_pending():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Get the first connected user
        cursor.execute("SELECT user_id, refresh_token FROM user_credentials LIMIT 1")
        user = cursor.fetchone()

        if not user:
            print("No connected SP-API users found.")
            conn.close()
            return

        user_id = user['user_id']
        refresh_token = user['refresh_token']
        print(f"Target User: {user_id}")

        # 2. Find Pending Deals (Present in deals, but NULL in user_restrictions for this user)
        # Note: We also target deals NOT in user_restrictions at all
        cursor.execute("""
            SELECT d.ASIN
            FROM deals d
            LEFT JOIN user_restrictions ur ON d.ASIN = ur.asin AND ur.user_id = ?
            WHERE ur.is_restricted IS NULL
        """, (user_id,))

        pending_asins = [row['ASIN'] for row in cursor.fetchall()]

        count = len(pending_asins)
        print(f"Found {count} pending ASINs.")

        if count == 0:
            print("No pending restrictions to check.")
            conn.close()
            return

        print("Triggering background task 'check_restriction_for_asins' for these items...")

        # We use check_restriction_for_asins because it handles token refresh internally
        # and iterates through users (though here we know the user, but the task is generic for ASINs)
        # Actually, check_restriction_for_asins checks ALL users. That's fine.

        # Send in batches of 50 to avoid overloading the worker queue or argument size limits
        BATCH_SIZE = 50
        for i in range(0, count, BATCH_SIZE):
            batch = pending_asins[i : i + BATCH_SIZE]
            celery_app.send_task('keepa_deals.sp_api_tasks.check_restriction_for_asins', args=[batch])
            print(f"  - Queued batch {i // BATCH_SIZE + 1} ({len(batch)} items)")

        print("Done. The background worker should process these shortly.")
        conn.close()

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    force_check_pending()
