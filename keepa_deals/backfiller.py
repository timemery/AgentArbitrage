from celery import Celery
import logging
import os
import time
from datetime import datetime, timedelta

from keepa_deals.db_utils import create_deals_table_if_not_exists, save_deals_to_db, clear_deals_table, save_watermark
from keepa_deals.keepa_api import fetch_product_batch, fetch_deals_for_deals
from keepa_deals.processing import _process_single_deal
from keepa_deals.token_manager import TokenManager
from worker import celery_app as celery
from .backfill_state import BackfillState
from keepa_deals.seller_info import get_seller_info_for_single_deal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BACKFILL_STATE_FILE = 'backfill_state.json'
DEALS_PER_PAGE = 50

@celery.task(name='keepa_deals.backfiller.backfill_deals')
def backfill_deals(reset=False):
    logging.info("Starting backfill_deals task with one-book-at-a-time strategy.")
    keepa_api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")
    if not keepa_api_key or not xai_api_key:
        logging.error("API keys not configured. Set KEEPA_API_KEY and XAI_TOKEN environment variables.")
        return

    create_deals_table_if_not_exists()
    token_manager = TokenManager(keepa_api_key)
    state = BackfillState(BACKFILL_STATE_FILE)

    if reset:
        logging.info("Resetting backfill state and clearing deals table.")
        state.reset()
        clear_deals_table()
        save_watermark((datetime.now() - timedelta(days=365)).isoformat())

    logging.info("Performing initial token sync with Keepa API.")
    token_manager.sync_tokens()
    logging.info(f"Initial token count: {token_manager.get_tokens_left()}")

    page = state.get_last_completed_page()
    total_pages = 0

    while True:
        page += 1
        logging.info(f"Processing page {page}.")

        # Step 1: Fetch a page of ASINs from Keepa's /deal endpoint
        logging.info(f"Fetching deals for page {page}...")
        try:
            estimated_cost = 10  # Safe estimate for /deal endpoint
            token_manager.request_permission_for_call(estimated_cost, f"Fetching deal page {page}")

            deals_response, _, tokens_left = fetch_deals_for_deals(page=page, api_key=keepa_api_key)
            if not deals_response or 'deals' not in deals_response or not deals_response['deals']:
                logging.info("No more deals found. Backfill complete.")
                break

            total_pages = deals_response.get('totalPages', total_pages)
            token_manager.update_after_call(tokens_left)

        except Exception as e:
            logging.error(f"Error fetching deals on page {page}: {e}")
            time.sleep(60)
            continue

        asins = [deal['asin'] for deal in deals_response['deals']['dr']]


        # Step 2: Process each ASIN individually to ensure data freshness
        all_deals_data = []
        for asin in asins:
            logging.info(f"--- Processing ASIN: {asin} ---")
            try:
                # A) Fetch complete product data with live offers
                estimated_cost = 7 # ~6 for offers, 1 for product
                token_manager.request_permission_for_call(estimated_cost, f"Fetching product data for {asin}")
                product_data, _, tokens_left, _ = fetch_product_batch(keepa_api_key, [asin], offers=20)
                token_manager.update_after_call(tokens_left)

                if not product_data or not product_data.get('products'):
                    logging.warning(f"Could not retrieve product data for ASIN {asin}. Skipping.")
                    continue
                product = product_data['products'][0]

                # B) Immediately find the lowest seller and fetch their data
                seller_cache = get_seller_info_for_single_deal(product, keepa_api_key, token_manager)

                # C) Process the deal with fresh product and seller data
                processed_deal = _process_single_deal(product, seller_cache, xai_api_key)
                if processed_deal:
                    all_deals_data.append(processed_deal)
                    logging.info(f"Successfully processed ASIN {asin}.")
                else:
                    logging.warning(f"Processing returned no data for ASIN {asin}. It might be excluded by a filter.")

                time.sleep(1) # Small delay to be respectful to APIs

            except Exception as e:
                logging.error(f"Error processing ASIN {asin}: {e}", exc_info=True)

        # Step 3: Save the fully processed deals for this page to the database
        if all_deals_data:
            logging.info(f"Saving {len(all_deals_data)} processed deals from page {page} to the database.")
            save_deals_to_db(all_deals_data)

            # --- CRITICAL: Restore missing task triggers ---
            new_asins = [d['ASIN'] for d in all_deals_data if 'ASIN' in d]
            if new_asins:
                celery.send_task('keepa_deals.sp_api_tasks.check_restriction_for_asins', args=[new_asins])
                logging.info(f"Triggered restriction check for {len(new_asins)} new ASINs.")

            # Trigger the refiller to keep existing deals fresh
            celery.send_task('keepa_deals.simple_task.update_recent_deals')
            logging.info("Triggered the update_recent_deals (refiller) task.")

        else:
            logging.warning(f"No deals from page {page} were successfully processed to be saved.")

        state.set_last_completed_page(page)
        logging.info(f"Finished page {page}. Current tokens: {token_manager.get_tokens_left()}")

        if page >= total_pages:
            logging.info(f"Reached the last page ({page}/{total_pages}). Backfill complete.")
            break

    logging.info("backfill_deals task finished.")
