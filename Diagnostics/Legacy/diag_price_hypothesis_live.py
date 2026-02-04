import os
import sys
import json
from dotenv import load_dotenv

# Add project root to path to allow importing project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.keepa_api import fetch_product_batch

def analyze_live_product_data(asin_to_check):
    """
    Fetches live product data from Keepa for a single ASIN to validate
    the hypothesis that 'Used - Current' price in stats matches the
    lowest-priced 'Used' offer.
    """
    load_dotenv()
    keepa_api_key = os.getenv("KEEPA_API_KEY")
    if not keepa_api_key:
        print("Error: KEEPA_API_KEY not found in .env file.")
        return

    print(f"--- Fetching live data for ASIN: {asin_to_check} ---")
    # CRITICAL CHANGE: Request live offer data by setting `offers=20`.
    # This will populate the `offerCSV` field in the offer objects.
    product_data, _, tokens_left, _ = fetch_product_batch(api_key=keepa_api_key, asins_list=[asin_to_check], offers=20)
    print(f"  (API tokens left: {tokens_left})")

    if not product_data or not product_data.get('products'):
        print("  Could not retrieve product data from Keepa API.")
        return

    product = product_data['products'][0]

    # 1. Get the 'Used - Current' price from the `stats` object
    stats_used_price = product.get('stats', {}).get('current', [])[1] if product.get('stats') and len(product.get('stats', {}).get('current', [])) > 1 else -1

    if stats_used_price == -1:
        print("  Stats 'Used - Current' Price: Not available")
    else:
        print(f"  Stats 'Used - Current' Price: {stats_used_price / 100:.2f}")

    # 2. Find the minimum total price from the live 'offers' array for 'Used' conditions
    min_offer_price = float('inf')
    lowest_offer_details = None
    used_offers_found = False
    used_condition_codes = {2, 3, 4, 5}  # Like New, Very Good, Good, Acceptable

    if 'offers' not in product or not product['offers']:
        print("  'offers' array not found or is empty in product data. Cannot compare.")
        return

    for offer in product.get('offers', []):
        condition_val = offer.get('condition')
        condition_code = None
        if isinstance(condition_val, dict):
            condition_code = condition_val.get('value')
        else: # It's an integer
            condition_code = condition_val

        if condition_code in used_condition_codes:
            used_offers_found = True
            offer_csv = offer.get('offerCSV', [])
            if len(offer_csv) >= 2:
                price_cents = offer_csv[0]
                shipping_cents = offer_csv[1] if offer_csv[1] != -1 else 0
                total_price_cents = price_cents + shipping_cents

                if total_price_cents < min_offer_price:
                    min_offer_price = total_price_cents
                    lowest_offer_details = {
                        "sellerId": offer.get('sellerId'),
                        "condition": offer.get('condition'),
                        "isFBA": "FBA" if offer.get('isFBA') else "FBM"
                    }

    if not used_offers_found:
        print("  No 'Used' condition offers found in the 'offers' array.")
        if stats_used_price == -1:
            print(f"  ✅ HYPOTHESIS CONFIRMED for ASIN {asin_to_check}: No 'Used' offers found, and no 'Used' price in stats.")
        else:
            print(f"  ❌ HYPOTHESIS FALSE for ASIN {asin_to_check}: No 'Used' offers found, but a 'Used' price exists in stats.")
        print("-" * 30)
        return

    print(f"  Lowest Priced 'Used' Offer : {min_offer_price / 100:.2f}")
    if lowest_offer_details:
        print(f"     - Seller ID: {lowest_offer_details['sellerId']} ({lowest_offer_details['isFBA']})")
        print(f"     - Condition: {lowest_offer_details['condition']}")

    # 3. Compare and conclude
    if stats_used_price == min_offer_price:
        print(f"  ✅ HYPOTHESIS CONFIRMED for ASIN {asin_to_check}: The prices match.")
    else:
        print(f"  ❌ HYPOTHESIS FALSE for ASIN {asin_to_check}: Prices DO NOT match. Stats: {stats_used_price}, Offer: {min_offer_price}")
    print("-" * 30)


if __name__ == "__main__":
    asins_to_test = ["1598162152", "0060502282", "1433682508", "0876205864"]
    for asin in asins_to_test:
        analyze_live_product_data(asin)
