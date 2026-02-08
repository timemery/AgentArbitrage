
import sqlite3
import os
import sys

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

def run_diagnostic():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Check for Connected Users
        cursor.execute("SELECT user_id, refresh_token FROM user_credentials")
        users = cursor.fetchall()

        if not users:
            print("\n[WARNING] No connected SP-API users found in 'user_credentials' table.")
            print("The restriction check task cannot run without a connected user.")
            conn.close()
            return

        print(f"\nFound {len(users)} connected user(s):")
        for user in users:
            user_id = user['user_id']
            token_preview = user['refresh_token'][:10] + "..." if user['refresh_token'] else "None"
            print(f"  - User ID: {user_id} (Token: {token_preview})")

        # 2. Analyze Deals for the First User (assuming single user context for now)
        active_user_id = users[0]['user_id']
        print(f"\nAnalyzing restriction status for User ID: {active_user_id}")

        # Total Deals
        cursor.execute("SELECT COUNT(*) FROM deals")
        total_deals = cursor.fetchone()[0]
        print(f"Total Deals in DB: {total_deals}")

        # Restriction Breakdown
        # Pending (NULL record in user_restrictions)
        cursor.execute("""
            SELECT COUNT(*)
            FROM deals d
            LEFT JOIN user_restrictions ur ON d.ASIN = ur.asin AND ur.user_id = ?
            WHERE ur.is_restricted IS NULL
        """, (active_user_id,))
        pending_count = cursor.fetchone()[0]

        # Error (-1)
        cursor.execute("""
            SELECT COUNT(*)
            FROM user_restrictions
            WHERE user_id = ? AND is_restricted = -1
        """, (active_user_id,))
        error_count = cursor.fetchone()[0]

        # Restricted (1)
        cursor.execute("""
            SELECT COUNT(*)
            FROM user_restrictions
            WHERE user_id = ? AND is_restricted = 1
        """, (active_user_id,))
        restricted_count = cursor.fetchone()[0]

        # Approved (0)
        cursor.execute("""
            SELECT COUNT(*)
            FROM user_restrictions
            WHERE user_id = ? AND is_restricted = 0
        """, (active_user_id,))
        approved_count = cursor.fetchone()[0]

        print("\n--- Restriction Status Breakdown ---")
        print(f"  Pending (Loading Spinner): {pending_count}")
        print(f"  Error (Broken/Failed):    {error_count}")
        print(f"  Restricted (Apply):       {restricted_count}")
        print(f"  Approved (Buy):           {approved_count}")

        print("-" * 30)
        total_checked = error_count + restricted_count + approved_count
        print(f"  Total Checked:            {total_checked}")
        print(f"  Coverage:                 {(total_checked / total_deals * 100) if total_deals > 0 else 0:.1f}%")

        if pending_count > 0:
            print(f"\n[CRITICAL] {pending_count} deals are stuck in 'Pending' state (Loading Animation).")
            print("This indicates the background task 'check_all_restrictions_for_user' failed to process them.")

            # Show a sample of pending ASINs
            cursor.execute("""
                SELECT d.ASIN, d.Title
                FROM deals d
                LEFT JOIN user_restrictions ur ON d.ASIN = ur.asin AND ur.user_id = ?
                WHERE ur.is_restricted IS NULL
                LIMIT 5
            """, (active_user_id,))
            sample_pending = cursor.fetchall()
            print("Sample Pending ASINs:")
            for row in sample_pending:
                print(f"  - {row['ASIN']}: {row['Title']}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    run_diagnostic()
