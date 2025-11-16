import os
import json
import logging
import sys
from dotenv import load_dotenv
from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch, fetch_seller_data
from keepa_deals.seller_info import get_all_seller_info
from keepa_deals.token_manager import TokenManager

# --- Configuration ---
LOG_FILE = 'diag_no_seller_log.json'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_diagnostic():
    """
    Diagnoses "No Seller Info" by fetching a live batch of deals and processing them
    in memory until a failure is found.
    """
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logging.error("KEEPA_API_KEY not found in .env file. Aborting.")
        return

    token_manager = TokenManager(api_key)
    token_manager.sync_tokens()

    # 1. Fetch a large batch of deals to get a good sample size
    logging.info("Fetching a page of recent deals from Keepa...")
    deal_response, _, tokens_left = fetch_deals_for_deals(0, api_key, use_deal_settings=True)
    token_manager.update_after_call(tokens_left)

    if not (deal_response and 'deals' in deal_response and deal_response['deals']['dr']):
        logging.error("Failed to fetch any deals from the API. Aborting.")
        return

    deals = deal_response['deals']['dr']
    logging.info(f"Fetched {len(deals)} deals to process.")

    # 2. Fetch full product data for all deals
    all_asins = [d['asin'] for d in deals]
    all_products_map = {}
    for i in range(0, len(all_asins), 100): # Process in chunks of 100
        batch_asins = all_asins[i:i+100]
        est_cost = 12 * len(batch_asins)
        token_manager.request_permission_for_call(est_cost)
        product_response, _, _, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
        if tokens_left is not None: token_manager.update_after_call(tokens_left)
        if product_response and 'products' in product_response:
            all_products_map.update({p['asin']: p for p in product_response['products']})
    logging.info(f"Fetched product data for {len(all_products_map)} ASINs.")

    # 3. Pre-fetch all seller data
    all_seller_ids = {
        offer['sellerId']
        for p in all_products_map.values()
        for offer in p.get('offers', []) if isinstance(offer, dict) and offer.get('sellerId')
    }
    seller_data_cache = {}
    if all_seller_ids:
        seller_id_list = list(all_seller_ids)
        for i in range(0, len(seller_id_list), 100):
            batch_ids = seller_id_list[i:i+100]
            token_manager.request_permission_for_call(1)
            seller_data, _, _, tokens_left = fetch_seller_data(api_key, batch_ids)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)
            if seller_data and 'sellers' in seller_data:
                seller_data_cache.update(seller_data['sellers'])
    logging.info(f"Fetched data for {len(seller_data_cache)} unique sellers.")

    # 4. Process each product until a failure is found
    logging.info("Processing deals in memory to find a failure...")
    failure_found = False
    for deal in deals:
        asin = deal['asin']
        if asin not in all_products_map:
            continue

        product_data = all_products_map[asin]
        seller_info = get_all_seller_info(product_data, seller_data_cache)

        # The condition we are looking for!
        if seller_info.get('Seller') == 'No Seller Info':
            logging.error(f"FAILURE FOUND FOR ASIN: {asin}")
            failure_found = True

            # Clear and write the log file for just this failing ASIN
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)

            with open(LOG_FILE, 'w') as f:
                log_data = {
                    "failing_asin": asin,
                    "calculated_seller_info": seller_info,
                    "raw_product_data": product_data
                }
                json.dump(log_data, f, indent=2)

            logging.info(f"Full raw data for failing ASIN {asin} has been written to {LOG_FILE}.")
            logging.info("Exiting script.")
            sys.exit(0) # Success, we found what we were looking for

    if not failure_found:
        logging.warning(f"Scan complete. No deals with 'No Seller Info' were found in the {len(deals)} deals processed.")
        logging.warning("This could mean the bug is rarer than expected, or has been fixed. Try running again to get a different sample.")

if __name__ == '__main__':
    run_diagnostic()
