import os
import sys
import logging
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_product_batch, fetch_deals_for_deals
from keepa_deals.processing import _process_single_deal
from keepa_deals.smart_ingestor import check_peek_viability
from keepa_deals.stable_calculations import infer_sale_events, analyze_sales_performance, _query_xai_for_reasonableness
from keepa_deals.token_manager import TokenManager

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def detailed_diagnosis(asin):
    logger.info(f"\n=== Detailed Diagnosis for ASIN: {asin} ===")
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")

    if not api_key:
        logger.error("KEEPA_API_KEY not found in .env")
        return

    # 1. Fetch Data (Mocking Smart Ingestor Stage 2)
    logger.info("Fetching full product data (days=365, history=1, offers=20)...")
    # Using a dummy TokenManager to respect rate limits if needed, but for 1 ASIN it's fine.
    token_manager = TokenManager(api_key)
    # fetch_product_batch does NOT accept token_manager, so we just call it.
    response, _, _, _ = fetch_product_batch(api_key, [asin], days=365, history=1, offers=20)

    if not response or 'products' not in response or not response['products']:
        logger.error("Keepa returned no product data.")
        return

    product_data = response['products'][0]
    title = product_data.get('title', 'Unknown Title')
    logger.info(f"Title: {title}")

    # 2. Check Peek Viability (Stage 1)
    stats = product_data.get('stats', {})
    is_peek_viable = check_peek_viability(stats)
    logger.info(f"Stage 1 (Peek Viability): {'PASS' if is_peek_viable else 'FAIL'}")
    if not is_peek_viable:
        logger.warning("  -> Deal would be rejected at Stage 1 (Peek).")
        # Continue anyway for diagnosis

    # 3. Check Inferred Sales (Logic: Offer Drops + Rank Drops)
    sale_events, total_drops = infer_sale_events(product_data)
    logger.info(f"Inferred Sales Events: {len(sale_events)} (from {total_drops} offer drops)")

    if len(sale_events) == 0:
        logger.error("  -> FAILING HERE: No sales inferred. 'List at' cannot be calculated.")
        # Check why
        csv = product_data.get('csv', [])
        if not csv:
            logger.error("     -> CSV data is missing entirely!")
        else:
            rank_history = csv[3] if len(csv) > 3 else []
            logger.info(f"     -> Rank History Points: {len(rank_history) if rank_history else 0}")
            if rank_history:
                logger.info(f"     -> Rank Sample: {rank_history[:10]} ...")

            # Check offer counts
            new_offers = csv[11] if len(csv) > 11 else []
            used_offers = csv[12] if len(csv) > 12 else []
            logger.info(f"     -> New Offer Count Points: {len(new_offers) if new_offers else 0}")
            if new_offers:
                 logger.info(f"     -> New Offers Sample: {new_offers[:10]} ...")
            logger.info(f"     -> Used Offer Count Points: {len(used_offers) if used_offers else 0}")
            if used_offers:
                 logger.info(f"     -> Used Offers Sample: {used_offers[:10]} ...")

    # 4. Check Sales Performance Analysis (List at calculation)
    logger.info("Running Sales Performance Analysis...")
    analysis = analyze_sales_performance(product_data, sale_events)
    peak_price = analysis.get('peak_price_mode_cents', -1)

    if peak_price == -1:
        logger.error("  -> FAILING HERE: 'peak_price_mode_cents' is -1. 'List at' is invalid.")
        logger.info(f"     -> Analysis Output: {analysis}")

        # Check XAI Reasonableness (Manual Call)
        # We need to simulate the inputs to _query_xai_for_reasonableness to see if IT rejected it.
        # But analyze_sales_performance calls it internally.
        # If sale_events > 0 but peak_price is -1, it likely means XAI rejected it.
        if len(sale_events) > 0:
            logger.warning("     -> Sales exist but price invalid. Suspect XAI Rejection.")
    else:
        logger.info(f"  -> PASS: Calculated 'List at': ${peak_price/100:.2f}")

    # 5. Full Processing Check
    logger.info("Running _process_single_deal (Full Pipeline)...")
    seller_cache = {}
    result = _process_single_deal(product_data, seller_cache, xai_api_key)

    if result:
        logger.info("SUCCESS: Deal Accepted.")
        logger.info(json.dumps(result, indent=2, default=str))
    else:
        logger.error("FAILURE: Deal Rejected by _process_single_deal.")

def main():
    # Pick an ASIN from the logs or a new one
    test_asins = [
        "1455616133", # The one that failed on 1yr Avg
        "1632907690", # The one that failed on Sales Inference
    ]

    for asin in test_asins:
        detailed_diagnosis(asin)

if __name__ == "__main__":
    main()
