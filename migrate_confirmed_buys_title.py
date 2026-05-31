import sqlite3
import os

def main():
    db_path = os.getenv('DATABASE_URL', 'deals.db')
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verify table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='confirmed_buys'")
    if not cursor.fetchone():
        print("confirmed_buys table doesn't exist.")
        return

    # Check if column exists
    cursor.execute("PRAGMA table_info(confirmed_buys)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "title" not in columns:
        print("Adding 'title' column to 'confirmed_buys' table...")
        cursor.execute("ALTER TABLE confirmed_buys ADD COLUMN title TEXT")
        conn.commit()
    else:
        print("'title' column already exists in 'confirmed_buys'.")
        
    print("Backfilling 'title' by looking up deals.Title...")
    
    # Only backfill if deals table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deals'")
    if cursor.fetchone():
        cursor.execute('''
            UPDATE confirmed_buys
            SET title = (
                SELECT Title
                FROM deals
                WHERE deals.ASIN = confirmed_buys.asin
                LIMIT 1
            )
            WHERE title IS NULL
        ''')
        print(f"Updated {cursor.rowcount} rows.")
        conn.commit()
    else:
        print("Deals table does not exist, skipping backfill.")
        
    conn.close()

if __name__ == '__main__':
    main()
