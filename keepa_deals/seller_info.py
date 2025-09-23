import logging
from .keepa_api import fetch_seller_data
from .stable_calculations import calculate_seller_quality_score
import json

logger = logging.getLogger(__name__)

# Constants
WAREHOUSE_SELLER_ID = 'A2L77EE7U53NWQ'
AMAZON_SELLER_ID = 'ATVPDKIKX0DER'

# Cache for seller data to avoid redundant API calls within a script run
seller_data_cache = {}

def _get_best_offer_analysis(product, api_key=None, token_manager=None):
    """
    Finds the best live offer by cross-referencing the 'stats.current' array
    with the 'offers' array to ensure price accuracy and retrieve seller info.
    """
    asin = product.get('asin', 'N/A')
    stats = product.get('stats', {})
    current_prices_from_stats = stats.get('current', [])
    
    # Indices for various "Current" prices in the stats.current array.
    price_indices = [0, 1, 2, 7, 10, 19, 20, 21, 22, 32]
    
    # Create a set of valid current prices from the reliable stats array.
    valid_stat_prices = set()
    for index in price_indices:
        if len(current_prices_from_stats) > index and current_prices_from_stats[index] is not None and current_prices_from_stats[index] > 0:
            valid_stat_prices.add(current_prices_from_stats[index])
            
    if not valid_stat_prices:
        logger.warning(f"ASIN {asin}: No valid current prices found in stats.current. Cannot determine best price.")
        return {'Best Price': '-', 'Seller ID': '-', 'Seller': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-'}

    # Now, find the best offer by iterating through the live offers and validating their price.
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

            # Get the most recent price from the offer's history
            offer_history = offer.get('offerCSV', [])
            if len(offer_history) >= 2:
                try:
                    price = int(offer_history[-2])
                    shipping = int(offer_history[-1])
                    if shipping == -1: shipping = 0
                    
                    # This is the crucial step: validate the offer's price against our set of true current prices.
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
        # Fallback: just use the minimum price from stats if no offer matches
        min_price_cents = min(valid_stat_prices)
        return {
            'Best Price': f"${min_price_cents / 100:.2f}",
            'Seller ID': 'N/A (No matching offer)',
            'Seller': 'N/A (No matching offer)',
            'Seller Rank': '-',
            'Seller_Quality_Score': '-'
        }
        
    # We have the best offer. Proceed to build the final analysis.
    best_seller_id = best_offer_details['seller_id']
    final_analysis = {
        'Best Price': f"${best_offer_details['price'] / 100:.2f}",
        'Seller ID': best_seller_id,
        'Seller': '-',
        'Seller Rank': '-',
        'Seller_Quality_Score': '-'
    }
    
    logger.info(f"ASIN {asin}: Found best price {final_analysis['Best Price']} from validated live offers, matched to Seller ID: {best_seller_id}")

    if not api_key or not best_seller_id:
        logger.warning(f"ASIN {asin}: Cannot fetch seller score. No API key or seller ID.")
        return final_analysis

    # Fetch seller data from the cache or API
    seller_data = seller_data_cache.get(best_seller_id)
    
    if not seller_data and token_manager:
        logger.info(f"ASIN {asin}: Seller data for ID {best_seller_id} not in cache. Fetching from API.")
        token_manager.request_permission_for_call(estimated_cost=1) # Cost for one seller
        seller_data_response, _, _ = fetch_seller_data(api_key, [best_seller_id])
        token_manager.update_from_response(seller_data_response)

        if seller_data_response and seller_data_response.get('sellers'):
            seller_data = seller_data_response['sellers'].get(best_seller_id)
            if seller_data:
                seller_data_cache[best_seller_id] = seller_data

    if seller_data:
        # Extract seller name
        final_analysis['Seller'] = seller_data.get('sellerName', 'N/A')

        # The cache should contain the raw seller data dictionary.
        # The previous logic was flawed. We directly use the 'seller_data' object.
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
        # If the seller data is not in the cache, it means the pre-fetch failed or missed this ID.
        # We do not make a new API call here to avoid rate-limiting issues.
        logger.warning(f"ASIN {asin}: Seller data for ID {best_seller_id} not found in pre-fetched cache. Score cannot be calculated.")
        final_analysis['Seller_Quality_Score'] = "Data Unavailable"

    return final_analysis

def get_all_seller_info(product, api_key=None, token_manager=None):
    """
    Public function to get all seller-related information in a single dictionary.
    """
    return _get_best_offer_analysis(product, api_key=api_key, token_manager=token_manager)