#!/usr/bin/env python3
import sys
import os
import logging
import json
from datetime import datetime

# Ensure local imports work
sys.path.append(os.getcwd())

from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch
from keepa_deals.stable_calculations import infer_sale_events, analyze_sales_performance, get_list_at_price
from keepa_deals.token_manager import TokenManager

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logger.error("KEEPA_API_KEY not found.")
        return

    tm = TokenManager(api_key)
    tm.sync_tokens()

    logger.info("Fetching a page of deals...")
    # Fetch 1 page of deals (should give ~100-150 deals)
    deal_response, consumed, left = fetch_deals_for_deals(0, api_key, sort_type=4, token_manager=tm)

    if not deal_response or 'deals' not in deal_response:
        logger.error("Failed to fetch deals.")
        return

    deals = deal_response['deals']['dr']
    logger.info(f"Fetched {len(deals)} deals.")

    # Process first 5 deals to debug
    batch_asins = [d['asin'] for d in deals[:5]]
    logger.info(f"Debugging first 5 ASINs: {batch_asins}")

    product_response, api_info, consumed, left = fetch_product_batch(api_key, batch_asins, days=1095, history=1, offers=20)

    if not product_response or 'products' not in product_response:
        logger.error("Failed to fetch product details.")
        return

    products = product_response['products']

    for product in products:
        asin = product['asin']
        title = product.get('title', 'N/A')
        logger.info(f"--- Analyzing ASIN: {asin} ({title}) ---")

        # 1. Infer Sales
        sale_events, drop_count = infer_sale_events(product)
        logger.info(f"Infer Sale Events: Found {len(sale_events)} sane sales out of {drop_count} offer drops.")

        if sale_events:
            last_sale = sale_events[-1]
            logger.info(f"Most recent sale: {last_sale['event_timestamp']} @ {last_sale['inferred_sale_price_cents']}")
        else:
            logger.warning("No sales inferred.")

        # 2. Analyze Performance
        analysis = analyze_sales_performance(product, sale_events)
        logger.info(f"Analysis Result: {json.dumps(analysis, indent=2)}")

        # 3. Get List At
        list_at = get_list_at_price(product) # This calls _get_analysis internaly, so we might see cached logs
        logger.info(f"Final 'List at': {list_at}")

        if list_at is None:
            logger.error(">>> DEAL REJECTED: Missing 'List at'")
        else:
            logger.info(">>> DEAL ACCEPTED")

if __name__ == "__main__":
    main()
