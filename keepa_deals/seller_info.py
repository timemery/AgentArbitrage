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
    It correctly parses FBA and FBM offers and compares them against aggregated stats
    to find the most accurate current price and seller.
    """
    asin = product.get('asin', 'N/A')
    logger.debug(f"ASIN {asin}: Analyzing offers to find the 'Now' price (lowest USED price).")

    offers = product.get('offers', [])
    stats = product.get('stats', {})

    # 1. Find the best live offer from the 'offers' list, correctly parsing price.
    best_live_offer = None
    lowest_offer_price = float('inf')

    if offers:
        for offer in offers:
            try:
                # Basic validation
                if not isinstance(offer, dict):
                    continue

                condition_data = offer.get('condition')
                if not isinstance(condition_data, dict) or condition_data.get('value') == 1:  # Skip NEW items
                    continue

                if offer.get('sellerId') == WAREHOUSE_SELLER_ID:
                    continue

                offer_history = offer.get('offerCSV', [])
                if len(offer_history) < 2:  # Must have at least timestamp and price
                    continue

                # --- Restore Original Parsing Logic ---
                # The offerCSV is a flat list of [timestamp, price, shipping, ...].
                # The last two elements are the most recent price and shipping.
                price = int(offer_history[-2])
                shipping = int(offer_history[-1])
                if shipping == -1: # Keepa uses -1 for unknown shipping
                    shipping = 0

                total_price = price + shipping

                if 0 < total_price < lowest_offer_price:
                    lowest_offer_price = total_price
                    best_live_offer = offer

            except (IndexError, TypeError, ValueError) as e:
                logger.warning(f"ASIN {asin}: Could not parse a specific offer. Error: {e}. Offer data: {offer}")
                continue

    # 2. Find the best price from the 'stats' object as a reference.
    best_stats_price = float('inf')
    stats_source = "N/A"

    stats_current_used = stats.get('current', [])[2] if stats.get('current') and len(stats['current']) > 2 else None
    if stats_current_used is not None and 0 < stats_current_used:
        best_stats_price = stats_current_used
        stats_source = "stats.current[2]"

    buy_box_price = stats.get('buyBoxUsedPrice')
    if buy_box_price is not None and 0 < buy_box_price < best_stats_price:
        best_stats_price = buy_box_price
        stats_source = "stats.buyBoxUsedPrice"

    # 3. Determine the final price and seller.
    final_price = None
    final_seller_id = None
    final_source = "N/A"

    # Compare the best price from the live offers list with the best price from the stats object.
    if best_live_offer and lowest_offer_price <= best_stats_price:
        # The best price was found in the offers list. This is the most reliable source.
        final_price = lowest_offer_price
        final_seller_id = best_live_offer.get('sellerId')
        final_source = f"live offer (seller: {final_seller_id})"
        logger.info(f"ASIN {asin}: Best price found in live offers: ${final_price/100:.2f}")
    elif best_stats_price != float('inf'):
        # The stats object has a better price, or no live offers were found.
        # We use the stats price but cannot reliably know the seller.
        final_price = best_stats_price
        final_seller_id = None  # Seller is unknown in this case.
        final_source = f"stats object ({stats_source})"
        logger.info(f"ASIN {asin}: Best price from stats object is superior: ${final_price/100:.2f}. No matching live offer.")
    else:
        # No price found in offers or stats.
        logger.warning(f"ASIN {asin}: No valid USED price found in any source.")
        return {'Now': '-', 'Seller ID': '-', 'Seller': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-'}

    logger.info(f"ASIN {asin}: Final 'Now' price is {final_price / 100:.2f} from '{final_source}'.")

    # --- Build the final result dictionary ---
    result = {
        'Price Now': f"${final_price / 100:.2f}" if final_price is not None else '-',
        'Best Price': f"${final_price / 100:.2f}" if final_price is not None else '-',
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
    else:
        # This handles the case where the best price came from stats.
        result['Seller'] = "(Price from Keepa stats)"


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