import logging
import os
import json
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch
from keepa_deals.token_manager import TokenManager
from keepa_deals.stable_calculations import _get_analysis, analyze_sales_performance, infer_sale_events

logging.basicConfig(level=logging.WARNING)

def run_estimation():
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("Error: KEEPA_API_KEY not found in .env")
        return

    tm = TokenManager(api_key)

    print("Fetching a batch of live deals from Keepa...")
    deals_response = fetch_deals_for_deals(0, api_key, token_manager=tm)

    if not deals_response or 'deals' not in deals_response:
        print("Failed to fetch deals.")
        return

    deals = deals_response.get('deals', [])
    print(f"Fetched {len(deals)} deals.")

    # We need the full product data to run the analysis
    asin_list = [deal[0] for deal in deals[:50]] # Let's test a sample of 50 to save tokens and time
    print(f"Fetching full product data for {len(asin_list)} ASINs...")

    product_response, _, _, _ = fetch_product_batch(api_key, asin_list, days=1095, history=1, offers=20)

    if not product_response or 'products' not in product_response:
        print("Failed to fetch product data.")
        return

    products = product_response.get('products', [])
    print(f"Retrieved data for {len(products)} products.")

    source_counts = {
        'Inferred Sales (Peak Mode)': 0,
        'Inferred Sales (Sparse)': 0,
        'Keepa Stats Fallback': 0,
        'None/Rejected': 0,
        'Error': 0
    }

    for product in products:
        try:
            sale_events, _ = infer_sale_events(product)
            analysis = analyze_sales_performance(product, sale_events)

            source = analysis.get('price_source', 'None')
            if source == 'Inferred Sales':
                source_counts['Inferred Sales (Peak Mode)'] += 1
            else:
                source_counts[source] = source_counts.get(source, 0) + 1

        except Exception as e:
            source_counts['Error'] += 1

    total_analyzed = len(products)

    print("\n--- Price Source Distribution (Sample Size: {}) ---".format(total_analyzed))
    for source, count in source_counts.items():
        percent = (count / total_analyzed) * 100 if total_analyzed > 0 else 0
        print(f"{source}: {count} ({percent:.1f}%)")

    print("\n--- Estimated Impact ---")
    inferred_only = source_counts['Inferred Sales (Peak Mode)'] + source_counts['Inferred Sales (Sparse)']
    inferred_percent = (inferred_only / total_analyzed) * 100 if total_analyzed > 0 else 0
    fallback = source_counts['Keepa Stats Fallback']
    fallback_percent = (fallback / total_analyzed) * 100 if total_analyzed > 0 else 0

    print(f"If we eliminate deals that rely on fallbacks, we would lose approximately {fallback_percent:.1f}% of deals.")
    print(f"We would keep {inferred_percent:.1f}% of deals (based purely on inferred sales).")

if __name__ == "__main__":
    run_estimation()
