
import sys
import os
import logging
import sqlite3
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.db_utils import DB_PATH, get_all_user_credentials
from keepa_deals.amazon_sp_api import refresh_sp_api_token, fetch_orders, fetch_order_items

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_sales_sync():
    print("--- Starting Sales Sync Diagnostic ---")
    print(f"Database Path: {DB_PATH}")

    # 1. Check Database Credentials
    print("\n[1/4] Checking User Credentials...")
    try:
        users = get_all_user_credentials()
        if not users:
            print("❌ FAIL: No user credentials found in database.")
            print("   Action: Go to Settings -> Manual Credentials Update and save your keys.")
            return

        print(f"✅ SUCCESS: Found {len(users)} connected user(s).")
        for u in users:
            print(f"   - User ID: {u['user_id']}")
    except Exception as e:
        print(f"❌ ERROR: Database read failed: {e}")
        return

    # 2. Test API Connectivity & Order Fetch
    print("\n[2/4] Testing SP-API Order Fetch (Last 365 Days)...")

    cutoff_date = (datetime.utcnow() - timedelta(days=365)).isoformat()

    for user in users:
        user_id = user['user_id']
        refresh_token = user['refresh_token']

        print(f"\n   Testing User: {user_id}")

        # A. Refresh Token
        access_token = refresh_sp_api_token(refresh_token)
        if not access_token:
            print("   ❌ FAIL: Could not refresh access token. Credentials may be invalid or expired.")
            continue
        print("   ✅ SUCCESS: Access Token refreshed.")

        # B. Fetch Orders
        print(f"   Fetching orders created after {cutoff_date}...")
        try:
            orders = fetch_orders(access_token, last_updated_after=cutoff_date)
            print(f"   ℹ️ API Response: Found {len(orders)} orders.")

            if len(orders) == 0:
                print("   ⚠️ WARNING: API returned 0 orders. This is the root cause.")
                print("      Possible reasons:")
                print("      1. 'Inventory and Order Tracking' Role missing in Seller Central App.")
                print("      2. No sales in the last 365 days.")
                print("      3. Wrong Marketplace ID (Default is US).")
            else:
                print("   ✅ SUCCESS: Orders retrieved from API.")

                # C. Check Order Items (for first order)
                first_order_id = orders[0]['AmazonOrderId']
                print(f"   [3/4] Testing Item Fetch for Order {first_order_id}...")
                items = fetch_order_items(access_token, first_order_id)
                if items:
                    print(f"   ✅ SUCCESS: Found {len(items)} items in order.")
                    print(f"      - First Item SKU: {items[0].get('SellerSKU')}")
                else:
                    print("   ❌ FAIL: Could not fetch order items.")
                    print("      This usually indicates the 'Inventory and Order Tracking' role is missing.")

        except Exception as e:
            print(f"   ❌ ERROR during API call: {e}")

    # 4. Check Database Write (Sales Ledger)
    print("\n[4/4] Checking Local Database (Sales Ledger)...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sales_ledger")
            count = cursor.fetchone()[0]
            print(f"   Current 'sales_ledger' row count: {count}")

            if count > 0:
                cursor.execute("SELECT sale_date, amazon_order_id, sku, sale_price FROM sales_ledger ORDER BY sale_date DESC LIMIT 3")
                print("   Latest 3 Entries:")
                for row in cursor.fetchall():
                    print(f"   - {row}")
    except Exception as e:
        print(f"   ❌ ERROR reading sales_ledger: {e}")

    print("\n--- Diagnostic Complete ---")

if __name__ == "__main__":
    debug_sales_sync()
