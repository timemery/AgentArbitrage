
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

SP_API_BASE_URL = os.getenv("SP_API_URL", "https://sandbox.sellingpartnerapi-na.amazon.com")

@celery_app.task(name='keepa_deals.inventory_import.fetch_existing_inventory_task')
def fetch_existing_inventory_task():
    """
    Fetches existing inventory from Amazon via SP-API Reports API.
    Report Type: GET_MERCHANT_LISTINGS_ALL_DATA
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
    Orchestrates the report request, download, and parsing.
    """
    # 1. Request Report
    report_id = _request_report(access_token)
    if not report_id:
        return

    # 2. Poll for Status
    document_id = _poll_report_status(report_id, access_token)
    if not document_id:
        return

    # 3. Get Document URL
    url, compression = _get_report_document_url(document_id, access_token)
    if not url:
        return

    # 4. Download & Parse
    _download_and_process_report(url, compression, user_id)

def _request_report(access_token):
    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports"
    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json'
    }
    payload = {
        "reportType": "GET_MERCHANT_LISTINGS_ALL_DATA",
        "marketplaceIds": ["ATVPDKIKX0DER"] # US
    }

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 202:
        report_id = resp.json()['reportId']
        logger.info(f"Report requested. ID: {report_id}")
        return report_id
    else:
        logger.error(f"Failed to request report: {resp.text}")
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

def _download_and_process_report(url, compression, user_id):
    logger.info("Downloading report...")
    resp = requests.get(url)
    resp.raise_for_status()

    content = resp.content
    # Handle compression if needed (GZIP is common but depends on API version/params)
    # The 'compressionAlgorithm' field tells us.
    if compression == 'GZIP':
        import gzip
        content = gzip.decompress(content)

    text_content = content.decode('utf-8', errors='replace') # TSV is usually ISO-8859-1 or UTF-8

    # Parse TSV
    # Merchant Listings Report headers roughly: item-name, item-description, listing-id, seller-sku, price, quantity, open-date, image-url, item-is-marketplace, product-id-type, zshop-shipping-fee, item-note, item-condition, zshop-category1, zshop-browse-path, zshop-storefront-feature, asin1, option-payment-type, generic-keywords, item-is-merchant-shipping, fulfillment-channel, zshop-boldface, product-id, merchant-shipping-group-name, progress-type

    reader = csv.DictReader(io.StringIO(text_content), delimiter='\t')

    items_to_insert = []

    for row in reader:
        # We need SKU, ASIN, Title, Quantity
        sku = row.get('seller-sku')
        asin = row.get('asin1')
        title = row.get('item-name')
        qty = row.get('quantity')

        if not sku or not asin:
            continue

        try:
            qty = int(qty) if qty else 0
        except:
            qty = 0

        # Only import if quantity > 0? Or import all?
        # User might want to see history. But for "Active Inventory", qty > 0.
        # Let's import all for ledger completeness, status 'PURCHASED' (since we own it).
        # If qty is 0, it might be sold out.
        # But for initial import, we care about what's in stock.
        # Actually, "Active Inventory" tab displays quantity_remaining > 0.

        items_to_insert.append({
            'asin': asin,
            'title': title,
            'sku': sku,
            'quantity_purchased': qty,
            'quantity_remaining': qty,
            'status': 'PURCHASED',
            'source': 'Imported',
            'buy_cost': None, # Unknown
            'purchase_date': datetime.utcnow() # Approximate
        })

    if not items_to_insert:
        logger.info("No items found in report.")
        return

    logger.info(f"Inserting/Updating {len(items_to_insert)} items into ledger.")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for item in items_to_insert:
            # Check if exists by SKU to avoid duplicates on re-run
            cursor.execute("SELECT id FROM inventory_ledger WHERE sku = ?", (item['sku'],))
            existing = cursor.fetchone()

            if existing:
                # Update quantity? Or skip?
                # Ideally we update quantity if it changed.
                # For now, let's update quantity_remaining
                cursor.execute("""
                    UPDATE inventory_ledger
                    SET quantity_remaining = ?, quantity_purchased = MAX(quantity_purchased, ?)
                    WHERE id = ?
                """, (item['quantity_remaining'], item['quantity_purchased'], existing[0]))
            else:
                cursor.execute("""
                    INSERT INTO inventory_ledger (asin, title, sku, quantity_purchased, quantity_remaining, status, source, buy_cost, purchase_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item['asin'], item['title'], item['sku'], item['quantity_purchased'], item['quantity_remaining'], item['status'], item['source'], item['buy_cost'], item['purchase_date']))

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
