import sqlite3
import os
import sys

# Define DB path (relative to repo root)
DB_PATH = './deals.db'

def main():
    print("=== Diagnosing Hidden Deals ===")

    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Total Deals
        cursor.execute("SELECT COUNT(*) FROM deals")
        total_deals = cursor.fetchone()[0]
        print(f"Total Deals in DB: {total_deals}")

        # 2. Get all deals
        cursor.execute("SELECT * FROM deals")
        all_deals = [dict(row) for row in cursor.fetchall()]

        visible_count = 0
        hidden_count = 0

        reasons = {
            "Profit <= 0": 0,
            "List_at Missing/Zero": 0,
            "1yr_Avg Missing/Invalid": 0
        }

        samples = {
            "Profit <= 0": [],
            "List_at Missing/Zero": [],
            "1yr_Avg Missing/Invalid": []
        }

        # Logic from wsgi_handler.py api_deals
        for deal in all_deals:
            is_visible = True
            hidden_reason = []

            # Helper for safe float conversion
            def safe_float(val):
                if val is None: return 0.0
                try:
                    if isinstance(val, str):
                        # Remove '$' and ',' before converting
                        val = val.replace('$', '').replace(',', '')
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0

            # Check Profit
            profit = safe_float(deal['Profit'])
            if profit <= 0:
                is_visible = False
                hidden_reason.append("Profit <= 0")
                reasons["Profit <= 0"] += 1
                if len(samples["Profit <= 0"]) < 3:
                    samples["Profit <= 0"].append(deal)

            # Check List_at
            list_at = safe_float(deal['List_at'])
            if list_at <= 0:
                is_visible = False
                hidden_reason.append("List_at Missing/Zero")
                reasons["List_at Missing/Zero"] += 1
                if len(samples["List_at Missing/Zero"]) < 3:
                    samples["List_at Missing/Zero"].append(deal)

            # Check 1yr_Avg
            avg_1yr_val = safe_float(deal['1yr_Avg'])
            avg_1yr_str = str(deal['1yr_Avg'])
            if avg_1yr_val == 0 or avg_1yr_str in ['-', 'N/A', '', '0', '0.00', '$0.00']:
                is_visible = False
                hidden_reason.append("1yr_Avg Missing/Invalid")
                reasons["1yr_Avg Missing/Invalid"] += 1
                if len(samples["1yr_Avg Missing/Invalid"]) < 3:
                    samples["1yr_Avg Missing/Invalid"].append(deal)

            if is_visible:
                visible_count += 1
            else:
                hidden_count += 1
                # print(f"Hidden ASIN: {deal['ASIN']} - Reasons: {', '.join(hidden_reason)}")

        print(f"\nVisible Deals: {visible_count}")
        print(f"Hidden Deals: {hidden_count}")

        print("\n--- Hidden Reasons Breakdown ---")
        # Note: A deal can have multiple reasons, so sum might > hidden_count
        for r, c in reasons.items():
            print(f"{r}: {c}")

        print("\n--- Sample Hidden Deals ---")
        for r, deal_list in samples.items():
            if deal_list:
                print(f"\nReason: {r}")
                for d in deal_list:
                    print(f"  ASIN: {d['ASIN']}, Title: {d['Title'][:50]}...")
                    print(f"    Profit: {d['Profit']}, List_at: {d['List_at']}, 1yr_Avg: {d['1yr_Avg']}")
                    print(f"    Price Now: {d.get('Price Now')}, Last Update: {d.get('last_update')}, Last Seen: {d.get('last_seen_utc')}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
