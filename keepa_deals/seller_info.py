import logging
from keepa_deals.keepa_api import fetch_seller_data
from keepa_deals.token_manager import TokenManager
from keepa_deals.business_calculations import load_settings
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEEPA_EPOCH = datetime(2011, 1, 1)

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
    min_price = float('inf')
    best_offer = None
    used_condition_codes = {2, 3, 4, 5}

    offers = product.get('offers')
    if offers:
        # Load settings once for default shipping logic
        settings = load_settings()
        default_shipping = settings.get('estimated_shipping_per_book', 0.0) * 100 # Convert to cents

        # Calculate freshness cutoff (e.g., 365 days)
        # Keepa timestamps are minutes since 2011-01-01
        now_keepa_minutes = int((datetime.now() - KEEPA_EPOCH).total_seconds() / 60)
        freshness_cutoff = now_keepa_minutes - (365 * 24 * 60) # 1 year ago

        for offer in offers:
            try:
                condition_val = offer.get('condition')
                condition_code = condition_val.get('value') if isinstance(condition_val, dict) else condition_val

                if condition_code in used_condition_codes:
                    # When using the `offers` parameter, price info is in `offerCSV`.
                    # The most recent entry is at the END of the list.
                    # Format is [..., timestamp, price_cents, shipping_cents]
                    offer_csv = offer.get('offerCSV', [])
                    if len(offer_csv) < 3: # Need timestamp, price, shipping
                        if len(offer_csv) == 2: # Legacy/Malformed?
                             pass # Proceed with caution if we assume missing TS? No, unsafe.
                        else:
                            logger.warning(f"Malformed offerCSV for ASIN {product.get('asin')}: {offer_csv}")
                            continue

                    ts = offer_csv[-3]
                    price = offer_csv[-2]
                    shipping_raw = offer_csv[-1]

                    # Freshness Check: Skip Zombie Offers (> 1 year old)
                    if ts < freshness_cutoff:
                        continue

                    # Check for FBA
                    is_fba_offer = offer.get('isFBA', False)

                    if shipping_raw == -1:
                        if is_fba_offer:
                            shipping_cost = 0 # FBA typically implies free shipping for Prime/threshold
                        else:
                            # Unknown shipping for MFN. User requested using default setting.
                            shipping_cost = default_shipping
                    else:
                        shipping_cost = shipping_raw

                    total_price = price + shipping_cost

                    if total_price < min_price:
                        min_price = total_price
                        best_offer = offer
            except (AttributeError, KeyError, TypeError, IndexError) as e:
                logger.error(f"Malformed offer found for ASIN {product.get('asin')}: {offer}. Error: {e}")
                continue

    # Load settings once for default shipping logic
    settings = load_settings()
    default_shipping = settings.get('estimated_shipping_per_book', 0.0) * 100 # Convert to cents

    # Calculate freshness cutoff (e.g., 365 days)
    # Keepa timestamps are minutes since 2011-01-01
    now_keepa_minutes = int((datetime.now() - KEEPA_EPOCH).total_seconds() / 60)
    freshness_cutoff = now_keepa_minutes - (365 * 24 * 60) # 1 year ago

    for offer in offers:
        try:
            condition_val = offer.get('condition')
            condition_code = condition_val.get('value') if isinstance(condition_val, dict) else condition_val

            if condition_code in used_condition_codes:
                # When using the `offers` parameter, price info is in `offerCSV`.
                # The most recent entry is at the END of the list.
                # Format is [..., timestamp, price_cents, shipping_cents]
                offer_csv = offer.get('offerCSV', [])
                if len(offer_csv) < 3: # Need timestamp, price, shipping
                    if len(offer_csv) == 2: # Legacy/Malformed?
                         pass # Proceed with caution if we assume missing TS? No, unsafe.
                    else:
                        logger.warning(f"Malformed offerCSV for ASIN {product.get('asin')}: {offer_csv}")
                        continue

                ts = offer_csv[-3]
                price = offer_csv[-2]
                shipping_raw = offer_csv[-1]

                # Freshness Check: Skip Zombie Offers (> 1 year old)
                if ts < freshness_cutoff:
                    continue

                # Check for FBA
                is_fba_offer = offer.get('isFBA', False)

                if shipping_raw == -1:
                    if is_fba_offer:
                        shipping_cost = 0 # FBA typically implies free shipping for Prime/threshold
                    else:
                        # Unknown shipping for MFN. User requested using default setting.
                        shipping_cost = default_shipping
                else:
                    shipping_cost = shipping_raw

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

    # Fallback: Check 'stats.current' if no valid offer was found in 'offers' array
    # This handles cases where 'offers' is stale/empty but 'stats' has a fresh price.
    try:
        stats = product.get('stats', {})
        current = stats.get('current', [])

        fallback_price = None
        condition = 4 # Default to Used - Good

        # 1. Try Used Price (Index 2)
        if len(current) > 2 and current[2] > 0:
            fallback_price = current[2]

        # 2. If Used Price is missing/invalid, check New Price (Index 1)
        # but only if competitive (User prefers Used First strategy)
        if (fallback_price is None or fallback_price <= 0) and len(current) > 1 and current[1] > 0:
            new_price = current[1]
            logger.info(f"ASIN {product.get('asin')}: Used price missing in stats. Checking New price: {new_price}")
            # Implicitly acceptable since we found no Used option
            fallback_price = new_price
            condition = 0 # New, unopened

        if fallback_price and fallback_price > 0:
            logger.info(f"ASIN {product.get('asin')}: Using stats fallback price: {fallback_price} (Condition: {condition})")
            # Return placeholders for unknown metadata
            # Seller ID "Unknown" prevents lookup failure but displays clearly
            return fallback_price, "Unknown", False, condition

    except Exception as e:
        logger.warning(f"ASIN {product.get('asin')}: Stats fallback check failed: {e}")

    return None, None, None, None
