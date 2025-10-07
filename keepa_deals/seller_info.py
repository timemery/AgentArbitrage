import logging
from .stable_calculations import calculate_seller_quality_score
import json

logger = logging.getLogger(__name__)

# Constants
WAREHOUSE_SELLER_ID = 'A2L77EE7U53NWQ'
AMAZON_SELLER_ID = 'ATVPDKIKX0DER'

# Cache for seller data. This cache MUST be populated by the calling task
# before this module's functions are called.
seller_data_cache = {}

def _get_best_offer_analysis(product):
    """
    Finds the best live offer by cross-referencing the 'stats.current' array
    with the 'offers' array and then looks up the seller info from the pre-populated cache.
    """
    asin = product.get('asin', 'N/A')
    stats = product.get('stats', {})
    current_prices_from_stats = stats.get('current', [])
    
    # Indices for various "Current" prices in the stats.current array.
    price_indices = [0, 1, 2, 7, 10, 19, 20, 21, 22, 32]
    
    valid_stat_prices = set()
    for index in price_indices:
        if len(current_prices_from_stats) > index and current_prices_from_stats[index] is not None and current_prices_from_stats[index] > 0:
            valid_stat_prices.add(current_prices_from_stats[index])
            
    if not valid_stat_prices:
        logger.warning(f"ASIN {asin}: No valid current prices found in stats.current. Cannot determine best price.")
        return {'Best Price': '-', 'Seller ID': '-', 'Seller': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-'}

    best_offer_details = {
        'price': float('inf'),
        'seller_id': None,
        'offer_obj': None
    }
    
    raw_offers = product.get('offers', [])
    if not raw_offers:
        logger.warning(f"ASIN {asin}: No offers array to search for seller, but found valid prices in stats: {valid_stat_prices}")
    else:
        for offer in raw_offers:
            if not isinstance(offer, dict) or offer.get('sellerId') == WAREHOUSE_SELLER_ID:
                continue

            offer_history = offer.get('offerCSV', [])
            if len(offer_history) >= 2:
                try:
                    price = int(offer_history[-2])
                    shipping = int(offer_history[-1])
                    if shipping == -1: shipping = 0
                    
                    if price in valid_stat_prices:
                        total_price = price + shipping
                        if total_price < best_offer_details['price']:
                            best_offer_details['price'] = total_price
                            best_offer_details['seller_id'] = offer.get('sellerId')
                            best_offer_details['offer_obj'] = offer
                except (ValueError, IndexError):
                    continue

    if best_offer_details['price'] == float('inf'):
        logger.warning(f"ASIN {asin}: Could not find any live offer whose price matched a valid price in stats.current. Stats prices: {valid_stat_prices}")
        min_price_cents = min(valid_stat_prices)
        return {
            'Best Price': f"${min_price_cents / 100:.2f}",
            'Seller ID': 'N/A (No matching offer)',
            'Seller': 'N/A (No matching offer)',
            'Seller Rank': '-',
            'Seller_Quality_Score': '-'
        }
        
    best_seller_id = best_offer_details['seller_id']
    final_analysis = {
        'Best Price': f"${best_offer_details['price'] / 100:.2f}",
        'Seller ID': best_seller_id,
        'Seller': '-',
        'Seller Rank': '-',
        'Seller_Quality_Score': '-'
    }
    
    if not best_seller_id:
        return final_analysis

    # Fetch seller data ONLY from the pre-populated cache.
    seller_data = seller_data_cache.get(best_seller_id)
    
    if seller_data:
        final_analysis['Seller'] = seller_data.get('sellerName', 'N/A')
        rating_count = seller_data.get('currentRatingCount', 0)
        
        if rating_count > 0:
            final_analysis['Seller Rank'] = rating_count
            rating_percentage = seller_data.get('currentRating', 0)
            positive_ratings = round((rating_percentage / 100.0) * rating_count)
            score = calculate_seller_quality_score(positive_ratings, rating_count)
            final_analysis['Seller_Quality_Score'] = f"{score:.2f}/10"
        else:
            final_analysis['Seller_Quality_Score'] = "New Seller"
    else:
        # If not in cache, log it and return defaults. The calling task is responsible for pre-fetching.
        logger.warning(f"ASIN {asin}: Seller data for ID {best_seller_id} not found in cache. This should have been pre-fetched.")
        final_analysis['Seller'] = "Data Not Cached"
        final_analysis['Seller Rank'] = "N/A"
        final_analysis['Seller_Quality_Score'] = "N/A"

    return final_analysis

def get_all_seller_info(product):
    """
    Public function to get all seller-related information in a single dictionary.
    Relies on a pre-populated cache for seller data.
    """
    return _get_best_offer_analysis(product)