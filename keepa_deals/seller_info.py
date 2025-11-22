import logging
from .stable_calculations import calculate_seller_quality_score
import json

logger = logging.getLogger(__name__)

# Constants
WAREHOUSE_SELLER_ID = 'A2L77EE7U53NWQ'

def _get_best_offer_analysis(product, seller_data_cache):
    """
    Finds the best live USED offer by validating live offer prices against the authoritative
    'stats.current' array. This ensures price accuracy and correctly retrieves seller info.
    """
    asin = product.get('asin', 'N/A')
    stats = product.get('stats', {})
    current_prices_from_stats = stats.get('current', [])

    # Create a set of valid current prices from the reliable stats array for USED conditions.
    # Indices are: 2 (Used), 19 (Used-LikeNew), 20 (Used-VeryGood), 21 (Used-Good), 22 (Used-Acceptable), 32 (BuyBoxUsed)
    price_indices = [2, 19, 20, 21, 22, 32]
    valid_stat_prices = set()
    for index in price_indices:
        if len(current_prices_from_stats) > index and current_prices_from_stats[index] is not None and current_prices_from_stats[index] > 0:
            valid_stat_prices.add(current_prices_from_stats[index])

    if not valid_stat_prices:
        logger.warning(f"ASIN {asin}: No valid USED prices found in stats.current. Cannot determine best price.")
        return {'Price Now': '-', 'Best Price': '-', 'Seller ID': '-', 'Seller': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-'}

    # Now, find the best offer by iterating through live offers and validating their price against our ground truth.
    best_offer_details = {
        'price': float('inf'),
        'seller_id': None,
        'offer_obj': None
    }

    raw_offers = product.get('offers', [])
    if not raw_offers:
        logger.warning(f"ASIN {asin}: No 'offers' array to search for a seller, but found valid prices in stats: {valid_stat_prices}")
    else:
        for offer in raw_offers:
            try:
                if not isinstance(offer, dict) or offer.get('sellerId') == WAREHOUSE_SELLER_ID:
                    continue

                # Skip NEW items
                condition_data = offer.get('condition')
                if not isinstance(condition_data, dict) or condition_data.get('value') == 1:
                    continue

                offer_history = offer.get('offerCSV', [])
                if len(offer_history) < 2:
                    continue

                # The price in the offerCSV is the base price without shipping.
                price = int(offer_history[-2])

                # This is the crucial validation step.
                if price in valid_stat_prices:
                    shipping = int(offer_history[-1])
                    if shipping == -1: shipping = 0
                    total_price = price + shipping

                    if total_price < best_offer_details['price']:
                        best_offer_details['price'] = total_price
                        best_offer_details['seller_id'] = offer.get('sellerId')
                        best_offer_details['offer_obj'] = offer
            except (ValueError, IndexError, TypeError) as e:
                logger.warning(f"ASIN {asin}: Could not parse a specific offer. Error: {e}. Offer data: {offer}")
                continue

    if best_offer_details['price'] == float('inf'):
        logger.warning(f"ASIN {asin}: Could not find any live offer whose base price matched a valid price in stats.current. Falling back to lowest stat price.")
        # Fallback: if no live offer's base price matches, use the minimum valid price from stats.
        min_price_cents = min(valid_stat_prices)
        return {
            'Price Now': f"${min_price_cents / 100:.2f}",
            'Best Price': f"${min_price_cents / 100:.2f}",
            'Seller ID': '-',
            'Seller': '(Price from Keepa stats)',
            'Seller Rank': '-',
            'Seller_Quality_Score': '-'
        }

    # We have found the best, validated live offer. Build the final result.
    best_seller_id = best_offer_details['seller_id']
    result = {
        'Price Now': f"${best_offer_details['price'] / 100:.2f}",
        'Best Price': f"${best_offer_details['price'] / 100:.2f}",
        'Seller ID': best_seller_id,
        'Seller': '-',
        'Seller Rank': '-',
        'Seller_Quality_Score': '-'
    }

    logger.info(f"ASIN {asin}: Found best validated price {result['Price Now']} from Seller ID: {best_seller_id}")

    # Fetch seller data from the pre-populated cache.
    if best_seller_id:
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
