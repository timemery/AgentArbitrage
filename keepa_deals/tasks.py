import logging
import os
import json
import logging
import os
import json
import sqlite3
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import redis

from celery_config import celery
from .db_utils import create_deals_table_if_not_exists, sanitize_col_name
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin
from .token_manager import TokenManager
from .field_mappings import FUNCTION_LIST
from .seller_info import get_all_seller_info
from .business_calculations import (
    load_settings as business_load_settings,
    calculate_total_amz_fees,
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
MAX_ASINS_PER_BATCH = 50
LOCK_KEY = "update_recent_deals_lock"
LOCK_TIMEOUT = 60 * 30  # 30 minutes


def _parse_price(value_str):
    if isinstance(value_str, (int, float)): return float(value_str)
    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']: return 0.0
    try: return float(value_str.strip().replace('$', '').replace(',', ''))
    except ValueError: return 0.0

def _parse_percent(value_str):
    if isinstance(value_str, (int, float)): return float(value_str)
    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']: return 0.0
    try: return float(value_str.strip().replace('%', ''))
    except ValueError: return 0.0


def _process_single_deal(product_data, api_key, token_manager, xai_api_key, business_settings, headers):
    asin = product_data.get('asin')
    if not asin:
        return None

    row_data = {'ASIN': asin}

    # 1. Initial data extraction from field_mappings
    for header, func in zip(headers, FUNCTION_LIST):
        if func:
            try:
                if func.__name__ in ['last_update', 'last_price_change']:
                    result = func(product_data, logger, product_data)
                elif func.__name__ == 'deal_found':
                    result = func(product_data, logger)
                elif func.__name__ == 'get_condition':
                    result = func(product_data, logger)
                else:
                    result = func(product_data)
                row_data.update(result)
            except Exception as e:
                logger.error(f"Function {func.__name__} failed for ASIN {asin}, header '{header}': {e}", exc_info=True)

    # 2. Seller Info
    try:
        seller_info = get_all_seller_info(product_data, api_key=api_key, token_manager=token_manager)
        row_data.update(seller_info)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to get seller info: {e}", exc_info=True)

    # 3. Business Calculations
    try:
        peak_price = _parse_price(row_data.get('Expected Peak Price', '0'))
        fba_fee = _parse_price(row_data.get('FBA Pick&Pack Fee', '0'))
        referral_percent = _parse_percent(row_data.get('Referral Fee %', '0'))
        best_price = _parse_price(row_data.get('Best Price', '0'))
        shipping_included_flag = str(row_data.get('Shipping Included', 'no')).lower() == 'yes'

        total_amz_fees = calculate_total_amz_fees(peak_price, fba_fee, referral_percent)
        all_in_cost = calculate_all_in_cost(best_price, total_amz_fees, business_settings, shipping_included_flag)
        profit_margin = calculate_profit_and_margin(peak_price, all_in_cost)
        min_listing = calculate_min_listing_price(all_in_cost, business_settings)

        row_data.update({
            'Total AMZ fees': total_amz_fees, 'All-in Cost': all_in_cost,
            'Profit': profit_margin['profit'], 'Margin': profit_margin['margin'],
            'Min. Listing Price': min_listing
        })
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed business calculations: {e}", exc_info=True)

    # 4. Analytics
    try:
        yr_avg_info = get_1yr_avg_sale_price(product_data, logger=logger)
        trend_info = get_trend(product_data, logger=logger)
        row_data.update(yr_avg_info)
        row_data.update(trend_info)

        discount_info = get_percent_discount(row_data.get('1yr. Avg.'), row_data.get('Best Price'), logger=logger)
        row_data.update(discount_info)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed analytics calculations: {e}", exc_info=True)

    # 5. Seasonality
    try:
        title = row_data.get('Title', '')
        categories = row_data.get('Categories - Sub', '')
        manufacturer = row_data.get('Manufacturer', '')
        detailed_season = classify_seasonality(title, categories, manufacturer, xai_api_key=xai_api_key)

        row_data['Detailed_Seasonality'] = "None" if detailed_season == "Year-round" else detailed_season
        row_data['Sells'] = get_sells_period(detailed_season)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed seasonality classification: {e}", exc_info=True)

    return row_data


@celery.task(name='keepa_deals.tasks.update_recent_deals')
def update_recent_deals():
    redis_client = redis.Redis.from_url(celery.conf.broker_url)
    lock = redis_client.lock(LOCK_KEY, timeout=LOCK_TIMEOUT)

    if not lock.acquire(blocking=False):
        logger.info("--- Task: update_recent_deals is already running. Skipping execution. ---")
        return

    try:
        logger.info("--- Task: update_recent_deals started ---")
        create_deals_table_if_not_exists()

        api_key = os.getenv("KEEPA_API_KEY")
        xai_api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            logger.error("KEEPA_API_KEY not set. Aborting.")
            return

        token_manager = TokenManager(api_key)
        business_settings = business_load_settings()

        logger.info("Step 1: Fetching recent deals...")
        deal_response = fetch_deals_for_deals(0, api_key, use_deal_settings=True)

        # Authoritatively update token manager with actual cost from the response
        tokens_consumed = deal_response.get('tokensConsumed', 0) if deal_response else 0
        token_manager.update_after_call(tokens_consumed)

        if not deal_response or 'deals' not in deal_response:
            logger.error("Step 1 Failed: No response from deal fetch.")
            return

        recent_deals = [d for d in deal_response.get('deals', {}).get('dr', []) if validate_asin(d.get('asin'))]
        if not recent_deals:
            logger.info("Step 1 Complete: No new valid deals found.")
            return
        logger.info(f"Step 1 Complete: Fetched {len(recent_deals)} deals.")

        logger.info("Step 2: Fetching product data for deals...")
        all_fetched_products = {}
        asin_list = [d['asin'] for d in recent_deals]

        for i in range(0, len(asin_list), MAX_ASINS_PER_BATCH):
            batch_asins = asin_list[i:i + MAX_ASINS_PER_BATCH]
            # Make a more token-efficient call and capture the actual cost.
            product_response, _, tokens_consumed = fetch_product_batch(
                api_key, batch_asins, history=0, offers=20
            )
            token_manager.update_after_call(tokens_consumed)

            if product_response and 'products' in product_response:
                for p in product_response['products']:
                    all_fetched_products[p['asin']] = p
        logger.info(f"Step 2 Complete: Fetched product data for {len(all_fetched_products)} ASINs.")

        logger.info("Step 3: Processing deals...")
        with open(HEADERS_PATH) as f:
            headers = json.load(f)

        rows_to_upsert = []
        for deal in recent_deals:
            asin = deal['asin']
            if asin not in all_fetched_products:
                continue

            product_data = all_fetched_products[asin]
            product_data.update(deal)

            processed_row = _process_single_deal(product_data, api_key, token_manager, xai_api_key, business_settings, headers)

            if processed_row:
                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                processed_row['source'] = 'upserter'
                rows_to_upsert.append(processed_row)
        logger.info(f"Step 3 Complete: Processed {len(rows_to_upsert)} deals.")

        if not rows_to_upsert:
            logger.info("No rows to upsert. Task finished.")
            return

        logger.info(f"Step 4: Upserting {len(rows_to_upsert)} rows into database...")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # The list of original headers from the JSON file defines the canonical order.
                original_headers = headers
                sanitized_headers = [sanitize_col_name(h) for h in original_headers]

                data_for_upsert = []
                for row_dict in rows_to_upsert:
                    # Build the tuple of values in the exact order of the original headers list.
                    # This ensures the data aligns perfectly with the sanitized headers in the SQL query.
                    row_tuple = tuple(row_dict.get(h) for h in original_headers)
                    data_for_upsert.append(row_tuple)

                upsert_sql = f"""
                INSERT INTO {TABLE_NAME} ({', '.join(f'"{h}"' for h in sanitized_headers)})
                VALUES ({', '.join(['?'] * len(sanitized_headers))})
                ON CONFLICT(ASIN) DO UPDATE SET
                  {', '.join(f'"{h}"=excluded."{h}"' for h in sanitized_headers if h != 'ASIN')}
                """

                cursor.executemany(upsert_sql, data_for_upsert)
                conn.commit()
                logger.info(f"Step 4 Complete: Successfully upserted/updated {cursor.rowcount} rows.")

        except sqlite3.Error as e:
            logger.error(f"Step 4 Failed: Database error during upsert: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Step 4 Failed: Unexpected error during upsert: {e}", exc_info=True)

        logger.info("--- Task: update_recent_deals finished ---")
    finally:
        lock.release()
        logger.info("--- Task: update_recent_deals finished and lock released. ---")