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
    
    # --- Find the definitive lowest USED price from all available data ---
    lowest_used_price = float('inf')
    source = "N/A"

    # 1. Check `stats.current` for USED price (index 2)
    if stats and 'current' in stats and len(stats['current']) > 2 and stats['current'][2] is not None and stats['current'][2] > 0:
        lowest_used_price = stats['current'][2]
        source = "stats.current[2]"

    # 2. Check `stats.buyBoxUsedPrice`
    if stats and 'buyBoxUsedPrice' in stats and stats['buyBoxUsedPrice'] is not None and stats['buyBoxUsedPrice'] > 0:
        if stats['buyBoxUsedPrice'] < lowest_used_price:
            lowest_used_price = stats['buyBoxUsedPrice']
            source = "stats.buyBoxUsedPrice"
    
    # 3. Iterate through `offers` for a potentially lower USED price
    if offers:
        for offer in offers:
            # We only care about USED offers (condition 2-6)
            condition = offer.get('condition', {}).get('value')
            if not isinstance(offer, dict) or offer.get('sellerId') == WAREHOUSE_SELLER_ID or condition == 1: # 1 is 'New'
                continue

            offer_history = offer.get('offerCSV', [])
            if len(offer_history) >= 2:
                try:
                    price = int(offer_history[-2])
                    shipping = int(offer_history[-1])
                    if shipping == -1: shipping = 0
                    total_price = price + shipping
                    
                    if total_price < lowest_used_price:
                        lowest_used_price = total_price
                        source = f"offer array (seller: {offer.get('sellerId')})"
                except (ValueError, IndexError):
                    continue

    if lowest_used_price == float('inf'):
        logger.warning(f"ASIN {asin}: No valid USED price found in stats or offers. 'Now' price will be empty.")
        return {'Now': '-', 'Seller ID': '-', 'Seller': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-'}

    logger.info(f"ASIN {asin}: Determined lowest USED price ('Now') is {lowest_used_price / 100:.2f} from '{source}'.")

    # --- Find Seller Info Associated with the Winning Price ---
    best_seller_id = None
    if offers:
        for offer in offers:
             if not isinstance(offer, dict): continue
             offer_history = offer.get('offerCSV', [])
             if len(offer_history) >= 2:
                try:
                    price = int(offer_history[-2])
                    shipping = int(offer_history[-1])
                    if shipping == -1: shipping = 0
                    if (price + shipping) == lowest_used_price:
                        best_seller_id = offer.get('sellerId')
                        break # Found the first matching seller
                except (ValueError, IndexError):
                    continue

    final_analysis = {
        'Now': f"${lowest_used_price / 100:.2f}",
        'Seller ID': best_seller_id or 'N/A',
        'Seller': '-',
        'Seller Rank': '-',
        'Seller_Quality_Score': '-'
    }
    logger.info(f"ASIN {asin}: Best price {final_analysis['Now']} from validated live offers, matched to Seller ID: {best_seller_id}")

    if not best_seller_id:
        logger.warning(f"ASIN {asin}: Cannot get seller score because no seller ID was found for the winning price.")
        return final_analysis

    # --- Retrieve Seller Data from Cache ---
    seller_data = seller_data_cache.get(best_seller_id)

    if seller_data:
        final_analysis['Seller'] = seller_data.get('sellerName', 'N/A')
        rating_count = seller_data.get('currentRatingCount', 0)
        
        if rating_count > 0:
            final_analysis['Seller Rank'] = rating_count
            rating_percentage = seller_data.get('currentRating', 0)
            positive_ratings = round((rating_percentage / 100.0) * rating_count)
            score = calculate_seller_quality_score(positive_ratings, rating_count)
            # Ensure score is formatted to one decimal place for consistency
            final_analysis['Seller_Quality_Score'] = f"{score:.1f}/5.0"
        else:
            final_analysis['Seller_Quality_Score'] = "New Seller"
    else:
        logger.warning(f"ASIN {asin}: No seller data found in cache for ID {best_seller_id}.")
        final_analysis['Seller'] = "No Seller Info"

    return final_analysis

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