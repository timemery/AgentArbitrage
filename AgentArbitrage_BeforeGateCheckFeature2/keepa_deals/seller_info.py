import logging
from keepa_deals.keepa_api import fetch_seller_data
from keepa_deals.token_manager import TokenManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONDITION_CODE_MAP = {
    0: 'New, unopened',
    1: 'New, open box',
    2: 'Used - Like New',
    3: 'Used - Very Good',
    4: 'Used - Good',
    5: 'Used - Acceptable',
    6: 'Used - Refurbished',
    7: 'Collectible - Like New',
    8: 'Collectible - Very Good',
    9: 'Collectible - Good',
    10: 'Collectible - Acceptable',
    11: 'New, other'
}

def get_seller_info_for_single_deal(product, api_key, token_manager: TokenManager):
    """
    Finds the lowest-priced used offer for a single product, fetches data
    for only that seller, and returns a cache containing their info.
    This is a major optimization to reduce token consumption.
    """
    # Reuse the exact logic from get_used_product_info to ensure consistency
    price_now, seller_id, is_fba, condition_code = get_used_product_info(product)

    if not seller_id:
        logger.warning(f"ASIN {product.get('asin')}: Could not determine the lowest-priced used seller.")
        return {}

    logger.info(f"ASIN {product.get('asin')}: Found lowest-priced seller: {seller_id}. Fetching their data.")

    # Estimate cost and wait for tokens
    estimated_cost = 1
    token_manager.request_permission_for_call(estimated_cost)

    # Fetch seller data from Keepa
    seller_data, _, _, tokens_left = fetch_seller_data(api_key, [seller_id])
    token_manager.update_after_call(tokens_left)

    if seller_data and seller_data.get('sellers'):
        return seller_data['sellers']
    else:
        logger.warning(f"ASIN {product.get('asin')}: Failed to fetch data for seller {seller_id}.")
        return {}


def get_all_seller_info(product_list, api_key, token_manager: TokenManager):
    """
    DEPRECATED METHOD.
    Collects all unique seller IDs from a list of products, fetches their data
    in a single batch call, and returns a dictionary mapping seller IDs to their info.
    """
    logger.warning("Using deprecated 'get_all_seller_info'. This is inefficient.")
    unique_seller_ids = set()
    for product in product_list:
        if 'sellerIds' in product and product['sellerIds'] is not None:
            # The API returns lists for different offer types (new, used, etc.)
            for seller_id_list in product['sellerIds']:
                if seller_id_list:
                    unique_seller_ids.update(seller_id_list)

    if not unique_seller_ids:
        logger.info("No seller IDs found in the product list.")
        return {}

    seller_ids_list = list(unique_seller_ids)
    logger.info(f"Found {len(seller_ids_list)} unique sellers. Fetching their data.")

    # Estimate cost and wait for tokens if necessary
    # Cost is 1 token per seller.
    estimated_cost = len(seller_ids_list)
    token_manager.request_permission_for_call(estimated_cost, f"Fetching {len(seller_ids_list)} sellers")

    # Fetch seller data from Keepa
    keepa = KeepaAPI(api_key)
    seller_data = keepa.get_seller_info(seller_ids_list)
    token_manager.update_after_call(seller_data.get('tokensLeft', token_manager.get_tokens_left()))

    if seller_data and seller_data.get('sellers'):
        return seller_data['sellers']
    else:
        logger.warning("Failed to fetch seller data from Keepa API.")
        return {}


def get_used_product_info(product):
    """
    Extracts information about the lowest-priced used offer from a product's data
    by correctly parsing the `offerCSV` field from live offer data.

    Returns a tuple: (price_in_cents, seller_id, is_fba, condition_code)
    or (None, None, None, None) if no used offer is found.
    """
    offers = product.get('offers')
    if not offers:
        return None, None, None, None

    min_price = float('inf')
    best_offer = None
    used_condition_codes = {2, 3, 4, 5}

    for offer in offers:
        try:
            condition_val = offer.get('condition')
            condition_code = condition_val.get('value') if isinstance(condition_val, dict) else condition_val

            if condition_code in used_condition_codes:
                # When using the `offers` parameter, price info is in `offerCSV`.
                # The most recent entry is at the END of the list.
                # Format is [..., timestamp, price_cents, shipping_cents]
                offer_csv = offer.get('offerCSV', [])
                if len(offer_csv) < 2: # Need at least price and shipping
                    logger.warning(f"Malformed offerCSV for ASIN {product.get('asin')}: {offer_csv}")
                    continue

                price = offer_csv[-2]
                shipping_cost = offer_csv[-1] if offer_csv[-1] != -1 else 0
                total_price = price + shipping_cost

                if total_price < min_price:
                    min_price = total_price
                    best_offer = offer
        except (AttributeError, KeyError, TypeError, IndexError) as e:
            logger.error(f"Malformed offer found for ASIN {product.get('asin')}: {offer}. Error: {e}")
            continue

    if best_offer:
        price_now = min_price
        seller_id = best_offer.get('sellerId')
        is_fba = best_offer.get('isFBA', False)

        condition_val = best_offer.get('condition')
        condition_code = condition_val.get('value') if isinstance(condition_val, dict) else condition_val

        return price_now, seller_id, is_fba, condition_code
    else:
        return None, None, None, None
