# Restore Dashboard Functionality
# keepa_deals/seller_info.py

import logging
from .stable_calculations import calculate_seller_quality_score
import json

logger = logging.getLogger(__name__)

# Constants
WAREHOUSE_SELLER_ID = 'A2L77EE7U53NWQ'

def _get_best_offer_analysis(product, seller_data_cache):
    """
    Finds the best live USED offer. This logic is critical for the 'Now' price.
    It ensures a value is always found if any USED price is available in the product data,
    without filtering out sellers.
    """
    asin = product.get('asin', 'N/A')
    logger.debug(f"ASIN {asin}: Analyzing offers to find the 'Now' price (lowest USED price).")

    stats = product.get('stats', {})
    offers = product.get('offers', [])
    
    # --- Final Refactored Logic ---
    
    lowest_offer_price = float('inf')
    best_seller_id_from_offers = None
    offer_source = "N/A"

    # 1. Find the best price from the OFFERS list first.
    if offers:
        for offer in offers:
            if not isinstance(offer, dict):
                logger.warning(f"ASIN {asin}: Skipping malformed offer: {offer}")
                continue

            condition = offer.get('condition', {}).get('value')
            seller_id = offer.get('sellerId')

            if condition == 1 or seller_id == WAREHOUSE_SELLER_ID:
                continue

            offer_history = offer.get('offerCSV', [])
            if len(offer_history) >= 2:
                try:
                    price = int(offer_history[-2])
                    shipping = int(offer_history[-1])
                    if shipping == -1: shipping = 0
                    total_price = price + shipping
                    
                    if 0 < total_price < lowest_offer_price:
                        lowest_offer_price = total_price
                        best_seller_id_from_offers = seller_id
                        offer_source = f"offer (seller: {seller_id})"
                except (ValueError, IndexError):
                    continue

    # 2. Compare the best offer price with prices from the STATS object.
    final_price = lowest_offer_price
    final_seller_id = best_seller_id_from_offers
    final_source = offer_source

    # Check stats.current[2] (USED price)
    if stats and 'current' in stats and len(stats['current']) > 2 and stats['current'][2] is not None and 0 < stats['current'][2] < final_price:
        final_price = stats['current'][2]
        final_seller_id = None # Invalidate seller ID, as this price isn't from a specific offer
        final_source = "stats.current[2]"

    # Check stats.buyBoxUsedPrice
    if stats and 'buyBoxUsedPrice' in stats and stats['buyBoxUsedPrice'] is not None and 0 < stats['buyBoxUsedPrice'] < final_price:
        final_price = stats['buyBoxUsedPrice']
        final_seller_id = None # Invalidate seller ID
        final_source = "stats.buyBoxUsedPrice"


    if final_price == float('inf'):
        logger.warning(f"ASIN {asin}: No valid USED price found in any source.")
        return {'Now': '-', 'Seller ID': '-', 'Seller': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-'}

    logger.info(f"ASIN {asin}: Final 'Now' price is {final_price / 100:.2f} from '{final_source}'.")

    # --- Build the final result dictionary ---
    result = {
        'Now': f"${final_price / 100:.2f}",
        'Seller ID': final_seller_id or '-',
        'Seller': '-',
        'Seller Rank': '-',
        'Seller_Quality_Score': '-'
    }

    # If we have a definitive seller ID, retrieve their data from the cache.
    if final_seller_id:
        seller_data = seller_data_cache.get(final_seller_id)
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
            logger.warning(f"ASIN {asin}: No data in cache for seller ID {final_seller_id}.")
            result['Seller'] = "No Seller Info"

    return result

def get_all_seller_info(product, seller_data_cache=None):
    """
    Public function to get all seller-related information in a single dictionary.
    This function now relies on a pre-populated cache of seller data and does not make API calls.
    """
    if seller_data_cache is None:
        # This provides a safeguard if the cache isn't passed, preventing crashes.
        # The caller (in tasks.py) is responsible for populating the cache.
        seller_data_cache = {}
    return _get_best_offer_analysis(product, seller_data_cache)