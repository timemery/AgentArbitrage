import os
import logging
from dotenv import load_dotenv
from keepa_deals.keepa_api import fetch_product_batch
from keepa_deals.new_analytics import get_1yr_avg_sale_price, get_percent_discount
from keepa_deals.seller_info import get_all_seller_info
from keepa_deals.token_manager import TokenManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def trace_asin_logic(api_key, asin):
    """Traces the data flow for calculating '% Down' for a specific ASIN."""
    logging.info(f"--- Tracing logic for ASIN: {asin} ---")

    # Instantiate a TokenManager since get_all_seller_info requires it
    token_manager = TokenManager(api_key)

    # 1. Fetch product data
    product_data, api_info, _ = fetch_product_batch(api_key, [asin])
    if not product_data or not product_data.get('products'):
        logging.error(f"Failed to fetch data for {asin}. API Info: {api_info}")
        return

    product = product_data['products'][0]
    logging.info("Successfully fetched product data.")

    # 2. Get 1-Year Average Sale Price
    avg_price_result = get_1yr_avg_sale_price(product, logger=logging)
    avg_price_str = avg_price_result.get("1yr. Avg.", "-")
    logging.info(f"Result from get_1yr_avg_sale_price: {avg_price_result}")

    # 3. Get Best Price (which is inside the seller info function)
    seller_info_result = get_all_seller_info(product, api_key=api_key, token_manager=token_manager)
    best_price_str = seller_info_result.get("Best Price", "-")
    logging.info(f"Result from get_all_seller_info (for Best Price): {seller_info_result}")

    # 4. Feed these exact values into the discount function
    logging.info(f"--- Calling get_percent_discount with: avg_price_str='{avg_price_str}', best_price_str='{best_price_str}' ---")
    percent_down_result = get_percent_discount(avg_price_str, best_price_str, logger=logging)

    # 5. Show final result
    logging.info(f"--- FINAL RESULT FOR '% Down' ---")
    print(percent_down_result)
    logging.info("---------------------------------")


if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        raise ValueError("KEEPA_API_KEY not found in .env file")

    asin_to_investigate = "0990926907"
    trace_asin_logic(api_key, asin_to_investigate)