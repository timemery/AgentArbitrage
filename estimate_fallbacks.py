import sqlite3
import json

def analyze_db():
    try:
        conn = sqlite3.connect('deals.db')
        cursor = conn.cursor()

        # We need to find the number of deals currently in the database
        cursor.execute("SELECT COUNT(*) FROM deals")
        total_deals = cursor.fetchone()[0]
        print(f"Total deals in database: {total_deals}")

        # We'll need to look at the deal data, possibly raw_keepa_data or similar,
        # or we can check the recent inferred sale price / list at price logic.
        cursor.execute("PRAGMA table_info(deals)")
        columns = [col[1] for col in cursor.fetchall()]
        print("Columns:", columns)

        if total_deals > 0:
            # Let's pull some records and re-run the logic or check if we store price_source
            cursor.execute("SELECT raw_keepa_data FROM deals LIMIT 100")
            rows = cursor.fetchall()

            # Since we can't easily re-run the logic on all deals without importing
            # stable_calculations, we can just run a python script that imports it.

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_db()
