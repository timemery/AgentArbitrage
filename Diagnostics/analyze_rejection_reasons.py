import os
import sys
import logging
import json
from datetime import datetime

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch
from keepa_deals.stable_calculations import infer_sale_events, analyze_sales_performance
from keepa_deals.token_manager import TokenManager
from keepa_deals.smart_ingestor import check_peek_viability

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def deep_dive_asin(product):
    asin = product.get('asin')
    title = product.get('title')
    print(f"\n--- Deep Dive for ASIN: {asin} ({title}) ---")

    # 0. Check Peek Viability (Stage 1)
    stats = product.get('stats', {})
    peek_passed = check_peek_viability(stats)
    print(f"Stage 1 (Peek Filter): {'PASSED' if peek_passed else 'FAILED'}")
    if not peek_passed:
        print("  -> NOTE: In a real run, this deal would be rejected here to save tokens.")
        print("     (Proceeding with full analysis anyway for diagnostics...)")

    # 1. Infer Sale Events
    sale_events, total_offer_drops = infer_sale_events(product)
    print(f"Total Offer Drops: {total_offer_drops}")
    print(f"Confirmed Sale Events: {len(sale_events)}")

    has_fallback = False
    candidates = []

    if len(sale_events) < 1:
        print("  -> INFERRED SALES FAILED (Count < 1)")
        # Check Fallback Candidates

        # Check specific indices used in fallback
        indices_to_check = [
            (2, 'Used'),
            (19, 'Used - Like New'),
            (20, 'Used - Very Good'),
            (21, 'Used - Good'),
            (22, 'Used - Acceptable'),
            (23, 'Collectible - Like New'),
            (24, 'Collectible - Very Good'),
            (25, 'Collectible - Good'),
            (26, 'Collectible - Acceptable')
        ]

        avg90_raw = stats.get('avg90', [])
        avg365_raw = stats.get('avg365', [])

        print("  -> Checking Fallback Candidates (Keepa Stats):")

        for idx, label in indices_to_check:
            val_90 = avg90_raw[idx] if len(avg90_raw) > idx else None
            val_365 = avg365_raw[idx] if len(avg365_raw) > idx else None

            # Logic from stable_calculations.py checks if val > 0
            # For 19, 20, 22 it also checks 'is not None'
            # But essentially if it is > 0 it is valid.

            valid_90 = val_90 is not None and val_90 > 0
            valid_365 = val_365 is not None and val_365 > 0

            print(f"     [{idx}] {label}: Avg90={val_90} ({'Valid' if valid_90 else 'Invalid'}), Avg365={val_365} ({'Valid' if valid_365 else 'Invalid'})")

            if valid_90 or valid_365:
                has_fallback = True
                candidates.append(max([v for v in [val_90, val_365] if v is not None and v > 0]))

        if has_fallback:
             print(f"  -> FALLBACK POSSIBLE. Max Candidate: {max(candidates)}")
        else:
             print("  -> FALLBACK FAILED. No valid Used price history in stats.")

    else:
        print("  -> INFERRED SALES SUCCESS")

    # 2. Analyze Sales Performance (Amazon Ceiling & XAI)
    print("  -> Running analyze_sales_performance...")
    # Mocking XAI env var if not set (though it should be set in .env)
    analysis = analyze_sales_performance(product, sale_events)

    print("  -> Analysis Result:")
    print(json.dumps(analysis, indent=4))

    peak_price = analysis.get('peak_price_mode_cents', -1)
    if peak_price == -1:
        print("  -> FINAL RESULT: REJECTED (Missing List at)")

        # Determine why
        if len(sale_events) < 1 and not has_fallback:
             print("     Reason: Inferred Sales < 1 AND Fallback Failed.")
        elif len(sale_events) >= 1 or has_fallback:
             # If we had candidates or sales, but result is -1, it must be XAI or Ceiling logic weirdness.
             # Note: Ceiling logic doesn't return -1, it caps.
             # So it must be XAI rejection.
             print("     Reason: XAI Reasonableness Check FAILED (or API Error/Limit).")
    else:
        print(f"  -> FINAL RESULT: ACCEPTED. List at: ${peak_price/100:.2f}")

def main():
    api_key = os.getenv('KEEPA_API_KEY')
    if not api_key:
        print("Error: KEEPA_API_KEY not found in environment.")
        return

    print("Fetching 10 deals from Keepa to analyze...")
    token_manager = TokenManager(api_key=api_key)

    # 1. Fetch Deals
    deals_response, _, _ = fetch_deals_for_deals(0, api_key, token_manager=token_manager)
    if not deals_response:
        print("Failed to fetch deals.")
        return

    deals = deals_response.get('deals', {}).get('dr', [])
    if not deals:
        print("No deals found in response.")
        return

    asins = [d['asin'] for d in deals[:10]] # Take first 10
    print(f"Fetched ASINs: {asins}")

    # 2. Fetch Full Product Data
    print("Fetching full product data...")
    products_response, _, _, _ = fetch_product_batch(api_key, asins, days=365, history=1)

    if not products_response:
         print("Failed to fetch products.")
         return

    products = products_response.get('products', [])

    # 3. Analyze Each
    for product in products:
        deep_dive_asin(product)

if __name__ == "__main__":
    main()
