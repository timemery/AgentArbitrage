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
    Extracts price and seller information using a 'Stats-First' strategy.

    1. Determines the base price from `stats.current` (guaranteed availability).
    2. Searches the `offers` array for an entry matching that price to enrich with Seller ID/FBA data.
    3. If no match is found in offers, returns the Stats price with generic Seller info.

    Returns a tuple: (price_in_cents, seller_id, is_fba, condition_code)
    or (None, None, None, None) if the product is effectively unavailable.
    """
    stats = product.get('stats', {})
    current = stats.get('current', [])

    # --- Step 1: Establish the "Source of Truth" Price from Stats ---
    target_price = None
    condition_code = 4 # Default to Used - Good

    # Priority A: Used Price (Index 2)
    if len(current) > 2 and current[2] > 0:
        target_price = current[2]
    # Priority B: New Price (Index 1) - Only if Used is missing
    elif len(current) > 1 and current[1] > 0:
        target_price = current[1]
        condition_code = 0 # New, unopened

    # If no valid price in stats, the item is unavailable.
    # Do NOT fallback to old offers.
    if not target_price or target_price <= 0:
        return None, None, None, None

    # --- Step 2: Attempt to Match with Seller Details in Offers ---
    offers = product.get('offers')
    best_match = None

    # Load settings for shipping logic
    settings = load_settings()
    default_shipping = settings.get('estimated_shipping_per_book', 0.0) * 100 # Convert to cents

    # Calculate freshness cutoff (e.g., 365 days) just to avoid matching ancient duplicates
    now_keepa_minutes = int((datetime.now() - KEEPA_EPOCH).total_seconds() / 60)
    freshness_cutoff = now_keepa_minutes - (365 * 24 * 60)

    if offers:
        for offer in offers:
            try:
                offer_cond_val = offer.get('condition')
                offer_cond = offer_cond_val.get('value') if isinstance(offer_cond_val, dict) else offer_cond_val

                # Loose condition matching: If target is Used, accept any Used. If New, accept New.
                is_target_used = (condition_code == 4)
                is_offer_used = (offer_cond in {2, 3, 4, 5})

                if is_target_used != is_offer_used:
                    continue

                offer_csv = offer.get('offerCSV', [])
                if len(offer_csv) < 3: continue

                ts = offer_csv[-3]
                item_price = offer_csv[-2]
                shipping_raw = offer_csv[-1]

                # Skip zombies when matching
                if ts < freshness_cutoff:
                    continue

                # Match Logic: stats.current is ITEM PRICE
                if item_price == target_price:
                    # Calculate Total Price (Landed)
                    is_fba_offer = offer.get('isFBA', False)
                    if shipping_raw == -1:
                        shipping_cost = 0 if is_fba_offer else default_shipping
                    else:
                        shipping_cost = shipping_raw

                    total_match_price = item_price + shipping_cost

                    # Save this as a candidate.
                    # If we find multiple matches, maybe pick the freshest?
                    # For now, first valid match is good enough.
                    return total_match_price, offer.get('sellerId'), is_fba_offer, offer_cond

            except (AttributeError, KeyError, TypeError, IndexError):
                continue

    # --- Step 3: No Match Found - Return Stats Price (Unknown Seller) ---
    # We must add default shipping since stats.current is just Item Price
    # Assumption: If we don't know the seller, we assume MFN + Default Shipping to be safe/conservative cost-wise.
    final_price = target_price + default_shipping

    # Log the fallback for debugging
    # logger.info(f"ASIN {product.get('asin')}: Using Stats price {target_price} + Def.Ship {default_shipping}. No offer match found.")

    return final_price, "Unknown", False, condition_code
