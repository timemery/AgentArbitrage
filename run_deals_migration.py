#!/usr/bin/env python3
"""
run_deals_migration.py

One-time migration script to repair deals.db rows:
1. Backs up deals.db with a timestamped filename.
2. Cleans List_at and Expected_Trough_Price to numeric floats.
3. Recalculates All_in_Cost, Total_AMZ_fees, Profit, Margin, and Min_Listing_Price across all deals.
4. Reports before and after row counts (total rows vs Profit > 0 AND List_at IS NOT NULL).
5. Displays 10 sample raw rows.
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from keepa_deals.db_utils import get_db_connection
from keepa_deals.recalculator import recalculate_deals

def run_migration():
    db_path = os.getenv('DATABASE_URL', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deals.db'))
    
    if not os.path.exists(db_path):
        print(f"Database file not found at '{db_path}'. Exiting.")
        sys.exit(1)

    print("=" * 70)
    print("STEP 1: CREATING DATABASE BACKUP")
    print("=" * 70)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{db_path}.bak-{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"Backup created successfully at: {backup_path}")
    print(f"Backup file size: {os.path.getsize(backup_path)} bytes")

    print("\n" + "=" * 70)
    print("STEP 2: CHECKING BEFORE-MIGRATION STATS")
    print("=" * 70)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM deals")
    total_before = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM deals WHERE Profit > 0 AND List_at IS NOT NULL')
    profit_gt_zero_before = cursor.fetchone()[0]

    print(f"  Total raw rows in deals.db: {total_before}")
    print(f"  Rows with Profit > 0 AND List_at IS NOT NULL: {profit_gt_zero_before}")
    conn.close()

    print("\n" + "=" * 70)
    print("STEP 3: RUNNING RECALCULATION & MIGRATION")
    print("=" * 70)
    recalculate_deals()

    print("\n" + "=" * 70)
    print("STEP 4: CHECKING AFTER-MIGRATION STATS")
    print("=" * 70)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM deals")
    total_after = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM deals WHERE Profit > 0 AND List_at IS NOT NULL')
    profit_gt_zero_after = cursor.fetchone()[0]

    print(f"  Total raw rows in deals.db: {total_after}")
    print(f"  Rows with Profit > 0 AND List_at IS NOT NULL: {profit_gt_zero_after}")

    print("\n" + "=" * 70)
    print("STEP 5: VERIFICATION QUERY (10 SAMPLE ROWS)")
    print("=" * 70)
    cursor.execute('''
        SELECT ASIN, Price_Now, List_at, All_in_Cost, Total_AMZ_fees, Profit
        FROM deals
        WHERE Profit IS NOT NULL
        LIMIT 10
    ''')
    rows = cursor.fetchall()
    print("ASIN, Price_Now, List_at, All_in_Cost, Total_AMZ_fees, Profit")
    print("-" * 70)
    for r in rows:
        print(f"{r[0]}, {r[1]}, {r[2]}, {r[3]}, {r[4]}, {r[5]}")

    conn.close()
    print("\nMigration complete!")

if __name__ == '__main__':
    run_migration()
