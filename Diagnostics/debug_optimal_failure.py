import sqlite3
import os
import sys

# Path to the database
DB_PATH = 'deals.db'

def diagnose_optimal_filters():
    print("--- Diagnostic: Optimal Filters Failure Analysis ---")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Check Total Deals
    try:
        cursor.execute("SELECT COUNT(*) FROM deals")
        total_deals = cursor.fetchone()[0]
        print(f"Total Deals in DB: {total_deals}")

        if total_deals == 0:
            print("(!) Database is empty. Please run a scan.")
            conn.close()
            return

    except sqlite3.Error as e:
        print(f"Database Error: {e}")
        conn.close()
        return

    # 2. Check Data Health (NULLs) for Critical Columns
    print("\n--- Data Health Check ---")
    critical_cols = [
        "Sales_Rank_Drops_last_30_days",
        "Deal_Trust",
        "Profit",
        "All_in_Cost",
        "Sales_Rank_Current",
        "AMZ"
    ]

    for col in critical_cols:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM deals WHERE \"{col}\" IS NULL")
            null_count = cursor.fetchone()[0]
            print(f"NULLs in '{col}': {null_count} / {total_deals}")
            if null_count == total_deals:
                print(f"  (!) ALL values are NULL. Filter on '{col}' will exclude EVERYTHING.")
        except sqlite3.Error:
            print(f"Column '{col}': MISSING (Schema Mismatch?)")

    # 3. Analyze Filter Attrition (Funnel)
    print("\n--- Filter Attrition Analysis (Optimal Settings) ---")
    # Optimal Settings: Profit $4, ROI 35%, Drops 1, Rank 250k, Trust 70%, Hide Gated (Skip), Hide AMZ

    # Define filters with their SQL (Sanitized)
    sanitized_profit = "CAST(REPLACE(REPLACE(\"Profit\", '$', ''), ',', '') AS REAL)"
    sanitized_cost = "CAST(REPLACE(REPLACE(\"All_in_Cost\", '$', ''), ',', '') AS REAL)"

    filters = [
        ("Base (Profit > 0, Data Exists)", f"({sanitized_profit} > 0 AND \"List_at\" > 0 AND \"1yr_Avg\" != 0)"),
        ("Min Profit $4", f"{sanitized_profit} >= 4"),
        ("Max Rank 250k", "\"Sales_Rank_Current\" <= 250000"),
        ("Min Drops 1", "\"Sales_Rank_Drops_last_30_days\" >= 1"),
        ("Min Trust 70%", "CAST(\"Deal_Trust\" AS INTEGER) >= 70"),
        ("Min ROI 35%", f"({sanitized_cost} > 0 AND (({sanitized_profit} * 1.0 / {sanitized_cost}) * 100) >= 35)"),
        ("Hide AMZ", "(\"AMZ\" IS NULL OR \"AMZ\" != '⚠️')")
    ]

    current_sql = "SELECT COUNT(*) FROM deals WHERE 1=1"

    for label, clause in filters:
        current_sql += f" AND {clause}"
        try:
            cursor.execute(current_sql)
            count = cursor.fetchone()[0]
            print(f"After applying '{label}': {count} deals remaining")

            if count == 0:
                print(f"  (!) STOP: '{label}' filtered out ALL remaining deals.")

                # Dig deeper: Why?
                # Check how many pass JUST this filter individually
                cursor.execute(f"SELECT COUNT(*) FROM deals WHERE {clause}")
                individual_count = cursor.fetchone()[0]
                print(f"      (Individually, {individual_count} deals pass '{label}')")
                break

        except sqlite3.Error as e:
            print(f"SQL Error applying '{label}': {e}")
            break

    conn.close()
    print("\n--- End Diagnostic ---")

if __name__ == "__main__":
    diagnose_optimal_filters()
