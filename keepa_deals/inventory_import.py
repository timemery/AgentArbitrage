
import os
import time
import requests
import csv
import io
import logging
import sqlite3
from datetime import datetime
from worker import celery_app
from keepa_deals.db_utils import DB_PATH, get_all_user_credentials
from keepa_deals.amazon_sp_api import refresh_sp_api_token

logger = logging.getLogger(__name__)

# Default to Production URL for safety in deployed environments.
# Strict multi-user design: Do not rely on .env for API credentials.
SP_API_BASE_URL = "https://sellingpartnerapi-na.amazon.com"

REPORT_TYPE_MERCHANT = "GET_MERCHANT_LISTINGS_ALL_DATA"
REPORT_TYPE_FBA = "GET_FBA_MYI_ALL_INVENTORY_DATA"

@celery_app.task(name='keepa_deals.inventory_import.fetch_existing_inventory_task')
def fetch_existing_inventory_task():
    """
    Fetches existing inventory from Amazon via SP-API Reports API.
    Report Types:
    1. GET_MERCHANT_LISTINGS_ALL_DATA (Active Listings)
    2. GET_FBA_MYI_ALL_INVENTORY_DATA (FBA Inventory)
    """
    logger.info("Starting inventory import task.")

    users = get_all_user_credentials()
    if not users:
        logger.warning("No connected users found for inventory import.")
        return "No users."

    for user in users:
        user_id = user['user_id']
        refresh_token = user['refresh_token']

        logger.info(f"Processing inventory import for user: {user_id}")

        access_token = refresh_sp_api_token(refresh_token)
        if not access_token:
            logger.error(f"Failed to refresh token for user {user_id}. Skipping.")
            continue

        try:
            _sync_user_inventory(user_id, access_token)
        except Exception as e:
            logger.error(f"Error syncing inventory for user {user_id}: {e}", exc_info=True)

    return "Inventory import completed."

def _sync_user_inventory(user_id, access_token):
    """
    Orchestrates the report request, download, and parsing for both Merchant and FBA reports.
    Includes retry logic for intermittent report generation failures.
    """
    report_types = [REPORT_TYPE_MERCHANT, REPORT_TYPE_FBA]

    for report_type in report_types:
        success = False
        attempts = 0
        max_attempts = 3

        while not success and attempts < max_attempts:
            attempts += 1
            try:
                logger.info(f"Requesting report: {report_type} (Attempt {attempts}/{max_attempts})")

                # 1. Request Report
                report_id = _request_report(access_token, report_type)
                if not report_id:
                    time.sleep(5) # Short wait before retry request
                    continue

                # 2. Poll for Status
                document_id = _poll_report_status(report_id, access_token)
                if not document_id:
                    logger.warning(f"Report {report_type} failed/cancelled. Retrying...")
                    time.sleep(30) # Wait before retrying entire flow
                    continue

                # 3. Get Document URL
                url, compression = _get_report_document_url(document_id, access_token)
                if not url:
                    continue

                # 4. Download & Parse
                _download_and_process_report(url, compression, user_id, report_type)
                success = True # Mark as success to exit retry loop

            except Exception as e:
                logger.error(f"Error processing report {report_type} for user {user_id}: {e}", exc_info=True)
                time.sleep(10) # Wait before retry
                # Continue to next attempt

        if not success:
            logger.error(f"Failed to process report {report_type} after {max_attempts} attempts.")

def _request_report(access_token, report_type):
    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports"
    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json'
    }
    payload = {
        "reportType": report_type,
        "marketplaceIds": ["ATVPDKIKX0DER"] # US
    }

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 202:
        report_id = resp.json()['reportId']
        logger.info(f"Report requested. ID: {report_id}")
        return report_id
    else:
        logger.error(f"Failed to request report {report_type}: {resp.text}")
        return None

def _poll_report_status(report_id, access_token):
    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports/{report_id}"
    headers = {'x-amz-access-token': access_token}

    # Poll for up to 5 minutes
    for _ in range(10): # 10 attempts * 30s = 5 min
        time.sleep(30)
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"Failed to check report status: {resp.text}")
            return None

        data = resp.json()
        status = data['processingStatus']
        logger.info(f"Report {report_id} status: {status}")

        if status == 'DONE':
            return data['reportDocumentId']
        elif status in ['CANCELLED', 'FATAL']:
            logger.error(f"Report processing failed with status: {status}")
            return None

    logger.error("Report processing timed out.")
    return None

def _get_report_document_url(document_id, access_token):
    url = f"{SP_API_BASE_URL}/reports/2021-06-30/documents/{document_id}"
    headers = {'x-amz-access-token': access_token}

    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return data['url'], data.get('compressionAlgorithm')
    else:
        logger.error(f"Failed to get document URL: {resp.text}")
        return None, None

def safe_int(val):
    """Helper to robustly convert values to integer, defaulting to 0."""
    try:
        return int(val) if val else 0
    except (ValueError, TypeError):
        return 0

def parse_inventory_report_content(text_content, report_type):
    """
    Parses the text content of an inventory report and returns a list of items to insert.
    """
    reader = csv.DictReader(io.StringIO(text_content), delimiter='\t')

    # Strip whitespace from headers
    if reader.fieldnames:
        reader.fieldnames = [x.strip() for x in reader.fieldnames]

    # --- Debug Logging: Log Headers ---
    try:
        headers = reader.fieldnames
        logger.info(f"CSV Headers for {report_type}: {headers}")
    except Exception as e:
        logger.warning(f"Could not log CSV headers: {e}")

    items_to_insert = []
    row_count = 0
    MAX_DEBUG_ROWS = 5

    for row in reader:
        row_count += 1

        # --- Debug Logging: Log Raw Row Data (First few rows) ---
        if row_count <= MAX_DEBUG_ROWS:
            logger.info(f"Processing Row {row_count} ({report_type}): {row}")

        if report_type == REPORT_TYPE_MERCHANT:
            # Merchant Listings Report headers
            sku = row.get('seller-sku')
            asin = row.get('asin1')
            title = row.get('item-name')
            qty = row.get('quantity')

            # Identify source
            fulfillment_channel = row.get('fulfillment-channel', 'DEFAULT')
            is_fba = fulfillment_channel == 'AMAZON_NA'

        elif report_type == REPORT_TYPE_FBA:
            # FBA Inventory Report headers
            sku = row.get('sku')
            asin = row.get('asin')
            title = row.get('product-name')

            # --- FBA Quantity Calculation (Feb 2026) ---
            # Sum of Fulfillable + Inbound (Working, Shipped, Receiving)
            # This ensures we count stock that is on the way to Amazon or being processed.

            fulfillable = safe_int(row.get('afn-fulfillable-quantity'))
            inbound_working = safe_int(row.get('afn-inbound-working-quantity'))
            inbound_shipped = safe_int(row.get('afn-inbound-shipped-quantity'))
            inbound_receiving = safe_int(row.get('afn-inbound-receiving-quantity'))

            qty = fulfillable + inbound_working + inbound_shipped + inbound_receiving

            # Debug log for breakdown if quantity > 0
            if qty > 0 and row_count <= MAX_DEBUG_ROWS:
                logger.info(f"FBA Qty Breakdown for {sku}: Total={qty} (Fulfillable={fulfillable}, Working={inbound_working}, Shipped={inbound_shipped}, Receiving={inbound_receiving})")

            is_fba = True

        else:
            logger.warning(f"Unknown report type: {report_type}")
            continue

        # --- Hardening: Strip whitespace from keys values to prevent mismatch ---
        if sku: sku = sku.strip()
        if asin: asin = asin.strip()
        # ----------------------------------------------------------------------

        if not sku:
            continue

        try:
            qty = int(qty) if qty else 0
        except:
            qty = 0

        # Log if we find FBA inventory > 0 (Already logged breakdown above for FBA)
        if is_fba and qty > 0 and row_count <= MAX_DEBUG_ROWS and report_type != REPORT_TYPE_FBA:
             logger.info(f"Found FBA Stock > 0: SKU={sku}, Qty={qty}")

        # Create item object
        item = {
            'asin': asin,
            'title': title,
            'sku': sku,
            'quantity': qty,
            'is_fba': is_fba,
            'status': 'PURCHASED',
            'source': 'Imported',
            'purchase_date': datetime.utcnow() # Approximate
        }
        items_to_insert.append(item)

    return items_to_insert

def _download_and_process_report(url, compression, user_id, report_type):
    logger.info(f"Downloading report {report_type}...")
    resp = requests.get(url)
    resp.raise_for_status()

    content = resp.content
    # Handle compression if needed (GZIP is common but depends on API version/params)
    if compression == 'GZIP':
        import gzip
        content = gzip.decompress(content)

    # 1. Decode with UTF-8-SIG to handle potential BOM
    text_content = content.decode('utf-8-sig', errors='replace')

    # 2. Parse Content
    items_to_insert = parse_inventory_report_content(text_content, report_type)

    if not items_to_insert:
        logger.info(f"No items found in report {report_type}.")
        return

    logger.info(f"Processing {len(items_to_insert)} items from report {report_type}.")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for item in items_to_insert:
            # Check if exists by SKU
            cursor.execute("SELECT id, quantity_remaining, quantity_purchased FROM inventory_ledger WHERE sku = ?", (item['sku'],))
            existing = cursor.fetchone()

            if existing:
                existing_id = existing[0]
                existing_qty_remaining = existing[1] or 0
                existing_qty_purchased = existing[2] or 0

                # Update Logic:
                # If Report is FBA (MYI), update quantity_remaining with FBA quantity.
                # If Report is Merchant, update quantity_remaining IF it's MFN. If it's FBA, ignore quantity (as it's often 0).

                new_qty_remaining = existing_qty_remaining
                new_qty_purchased = existing_qty_purchased

                if report_type == REPORT_TYPE_FBA:
                    # FBA report is authoritative for FBA stock
                    new_qty_remaining = item['quantity']
                    # Also update purchased if remaining > purchased (e.g. initial sync)
                    new_qty_purchased = max(existing_qty_purchased, item['quantity'])

                elif report_type == REPORT_TYPE_MERCHANT:
                    if not item['is_fba']:
                        # MFN item in Merchant report is authoritative for MFN stock
                        new_qty_remaining = item['quantity']
                        new_qty_purchased = max(existing_qty_purchased, item['quantity'])
                    else:
                        # FBA item in Merchant report usually has qty 0.
                        pass

                cursor.execute("""
                    UPDATE inventory_ledger
                    SET quantity_remaining = ?, quantity_purchased = ?
                    WHERE id = ?
                """, (new_qty_remaining, new_qty_purchased, existing_id))

            else:
                # Insert new item
                if item['asin']:
                    cursor.execute("""
                        INSERT INTO inventory_ledger (asin, title, sku, quantity_purchased, quantity_remaining, status, source, buy_cost, purchase_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (item['asin'], item['title'], item['sku'], item['quantity'], item['quantity'], item['status'], item['source'], None, item['purchase_date']))
                else:
                    logger.warning(f"Skipping new item insert for SKU {item['sku']} from report {report_type} due to missing ASIN.")

        conn.commit()

def process_bulk_cost_upload(csv_content):
    """
    Parses a CSV upload to update buy costs.
    Expected columns: SKU, Buy Cost, Purchase Date
    """
    try:
        # Handle potential BOM or encoding issues
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode('utf-8-sig') # Handle BOM

        reader = csv.DictReader(io.StringIO(csv_content))

        updated_count = 0

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            for row in reader:
                sku = row.get('SKU')
                buy_cost = row.get('Buy Cost')
                purchase_date = row.get('Purchase Date')

                if not sku or not buy_cost:
                    continue

                # Sanitize
                try:
                    buy_cost = float(buy_cost.replace('$', '').replace(',', ''))
                except ValueError:
                    continue # Skip invalid cost

                # Update
                # Only update if currently NULL or we want to overwrite?
                # Overwriting is better for "Fixing" mistakes.

                sql = "UPDATE inventory_ledger SET buy_cost = ?"
                params = [buy_cost]

                if purchase_date:
                    sql += ", purchase_date = ?"
                    params.append(purchase_date)

                sql += " WHERE sku = ?"
                params.append(sku)

                cursor.execute(sql, params)
                updated_count += cursor.rowcount

            conn.commit()

        return updated_count
    except Exception as e:
        logger.error(f"Error processing bulk cost upload: {e}", exc_info=True)
        raise e

def export_missing_costs_csv():
    """
    Generates a CSV string for items with missing buy costs.
    Columns: SKU, Title, ASIN, Buy Cost, Purchase Date
    """
    try:
        output = io.StringIO()
        writer = csv.writer(output)

        # Headers
        writer.writerow(['SKU', 'Title', 'ASIN', 'Buy Cost', 'Purchase Date'])

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Select items where buy_cost is NULL or 0
            cursor.execute("""
                SELECT sku, title, asin
                FROM inventory_ledger
                WHERE buy_cost IS NULL OR buy_cost = 0
                ORDER BY title
            """)

            rows = cursor.fetchall()
            for row in rows:
                # SKU, Title, ASIN, Buy Cost (Empty), Purchase Date (Empty)
                writer.writerow([row[0], row[1], row[2], '', ''])

        return output.getvalue()
    except Exception as e:
        logger.error(f"Error generating missing costs CSV: {e}", exc_info=True)
        raise e
