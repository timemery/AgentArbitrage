
import logging
from .stable_calculations import calculate_seller_quality_score

logger = logging.getLogger(__name__)

# --- Constants ---
WAREHOUSE_SELLER_ID = 'A2L77EE7U53NWQ'
AMAZON_SELLER_ID = 'ATVPDKIKX0DER'
CONDITION_CODE_MAP = {
    1: "New",
    2: "Used - Like New",
    3: "Used - Very Good",
    4: "Used - Good",
    5: "Used - Acceptable",
    10: "Collectible - Like New",
    11: "Collectible - Very Good",
}

def _get_best_offer_analysis(product, seller_data_cache):
    """
    Finds the best (lowest total price) live "Used" offer directly from the offers array.
    This is the most reliable way to get an actionable price and seller information.
    """
    asin = product.get('asin', 'N/A')
    raw_offers = product.get('offers', [])

    best_offer_details = {
        'total_price': float('inf'),
        'seller_id': None,
        'offer_obj': None,
        'condition': None
    }

    if not raw_offers:
        logger.warning(f"ASIN {asin}: No 'offers' array found. Cannot determine best price.")
    else:
        for offer in raw_offers:
            try:
                # Basic validation and filtering
                if not isinstance(offer, dict):
                    continue
                if offer.get('sellerId') in [WAREHOUSE_SELLER_ID, AMAZON_SELLER_ID]:
                    continue

                # We are only interested in "Used" items (condition != 1)
                condition_data = offer.get('condition')
                condition_value = None
                if isinstance(condition_data, dict):
                    condition_value = condition_data.get('value')
                elif isinstance(condition_data, int):
                    condition_value = condition_data

                if condition_value == 1: # 1 is "New"
                    continue

                # The most recent price and shipping are at the end of offerCSV
                offer_history = offer.get('offerCSV', [])
                if len(offer_history) < 2:
                    continue

                price = int(offer_history[-2])
                shipping = int(offer_history[-1])
                if shipping == -1: shipping = 0 # -1 means shipping is not specified, treat as 0 for FBA/Prime

                total_price = price + shipping

                if total_price < best_offer_details['total_price']:
                    best_offer_details['total_price'] = total_price
                    best_offer_details['seller_id'] = offer.get('sellerId')
                    best_offer_details['offer_obj'] = offer

                    # Determine the condition string
                    if isinstance(condition_data, dict):
                        best_offer_details['condition'] = condition_data.get('name', 'Used')
                    elif isinstance(condition_value, int):
                        best_offer_details['condition'] = CONDITION_CODE_MAP.get(condition_value, f'Used ({condition_value})')
                    else:
                        best_offer_details['condition'] = 'Used'

            except (ValueError, IndexError, TypeError) as e:
                logger.warning(f"ASIN {asin}: Could not parse a specific offer. Error: {e}. Offer data: {offer}")
                continue

    # If after checking all offers, we still haven't found a used one, the deal is invalid.
    if best_offer_details['total_price'] == float('inf'):
        logger.error(f"ASIN {asin}: No valid 'Used' offers found in the offers array. This deal will be excluded.")
        return None

    # We found a winning offer. Now, build the results and enrich with seller data.
    best_seller_id = best_offer_details['seller_id']
    result = {
        'Price Now': f"${best_offer_details['total_price'] / 100:.2f}",
        'Best Price': f"${best_offer_details['total_price'] / 100:.2f}",
        'Seller ID': best_seller_id,
        'Seller': 'N/A',
        'Seller Rank': '-',
        'Seller_Quality_Score': '-',
        'Condition': best_offer_details['condition']
    }

    logger.info(f"ASIN {asin}: Found best 'Used' offer. Price: {result['Price Now']}, Seller ID: {best_seller_id}")

    if best_seller_id and seller_data_cache:
        seller_data = seller_data_cache.get(best_seller_id)
        if seller_data:
            result['Seller'] = seller_data.get('sellerName', 'N/A')
            rating_count = seller_data.get('currentRatingCount', 0)

            if rating_count > 0:
                result['Seller Rank'] = rating_count
                rating_percentage = seller_data.get('currentRating', 0)
                positive_ratings = round((rating_percentage / 100.0) * rating_count)
                score = calculate_seller_quality_score(positive_ratings, rating_count)
                result['Seller_Quality_Score'] = f"{score:.1f}/5.0"
            else:
                result['Seller_Quality_Score'] = "New Seller"
        else:
            logger.warning(f"ASIN {asin}: No data in cache for seller ID {best_seller_id}.")
            result['Seller'] = "No Seller Info"

    return result

def get_all_seller_info(product, seller_data_cache=None):
    """
    Public function to get all seller-related information in a single dictionary.
    This function relies on a pre-populated cache of seller data.
    """
    if seller_data_cache is None:
        seller_data_cache = {}
    return _get_best_offer_analysis(product, seller_data_cache)
