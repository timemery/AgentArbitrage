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
            # --- Robustness Fix ---
            # This entire block is wrapped in a try/except and contains multiple checks
            # to handle malformed data from the Keepa API gracefully without crashing or flooding logs.
            try:
                # 1. Ensure the offer itself is a dictionary.
                if not isinstance(offer, dict):
                    continue

                # 2. Ensure the 'condition' field is a dictionary before accessing its 'value'.
                condition_data = offer.get('condition')
                if not isinstance(condition_data, dict):
                    continue

                condition = condition_data.get('value')
                seller_id = offer.get('sellerId')

                # Skip NEW items or Amazon Warehouse deals.
                if condition == 1 or seller_id == WAREHOUSE_SELLER_ID:
                    continue

                # Correctly parse the offerCSV to find the most recent price and shipping
                offer_history = offer.get('offerCSV', [])
                is_fba = offer.get('isFBA', False)

                # The last value is always stock, the one before is price.
                # For FBM, the value before price *might* be shipping.
                # We need to parse the history to find the most recent price point.

                # --- FINAL, DATA-DRIVEN PARSING LOGIC ---
                offer_history = offer.get('offerCSV', [])
                is_fba = offer.get('isFBA', False)

                if len(offer_history) < 2:
                    continue

                price = int(offer_history[-2])
                shipping = 0

                if not is_fba:
                    # For FBM offers, the last element is shipping, not stock.
                    shipping = int(offer_history[-1])
                    if shipping == -1: shipping = 0

                total_price = price + shipping

                if 0 < total_price < lowest_offer_price:
                    lowest_offer_price = total_price
                    best_seller_id_from_offers = seller_id
                    offer_source = f"offer (seller: {seller_id})"

            except (IndexError, TypeError, ValueError) as e:
                logger.warning(f"ASIN {asin}: Could not parse offer. Error: {e}. Offer data: {offer}")
                continue

    # 2. Compare the best offer price with prices from the STATS object.
    final_price = lowest_offer_price
    final_seller_id = best_seller_id_from_offers
    final_source = offer_source

    logger.info(f"ASIN {asin} [SELLER DEBUG]: After offers loop - lowest_offer_price: {lowest_offer_price}, seller_id: {best_seller_id_from_offers}")

    # --- Data Logic Fix ---
    # Store all seller prices from the offers loop to re-associate them later.
    offer_prices_to_seller_ids = {}
    if offers:
        for offer in offers:
            try:
                if isinstance(offer, dict):
                    is_fba = offer.get('isFBA', False)
                    price = int(offer.get('offerCSV', [])[-2])
                    shipping = 0
                    if not is_fba:
                        shipping = int(offer.get('offerCSV', [])[-1])
                        if shipping == -1: shipping = 0
                    total_price = price + shipping
                    seller_id = offer.get('sellerId')
                    if seller_id:
                        offer_prices_to_seller_ids[total_price] = seller_id
            except (IndexError, TypeError, ValueError):
                continue

    # --- Final, Simplified Logic ---
    # Find the best price from the STATS object.
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

    # Compare the best offer price with the best stats price and decide.
    if final_price <= best_stats_price:
        # The best price is from a specific offer, which we already have.
        logger.info(f"ASIN {asin} [SELLER DEBUG]: Best price is from OFFERS: ${final_price/100:.2f}, Seller: {final_seller_id}")
    elif offer_prices_to_seller_ids:
        # The stats price is better, AND we have offers to associate with.
        # Find the closest offer for data integrity.
        closest_offer_price = min(offer_prices_to_seller_ids.keys(), key=lambda k: abs(k - best_stats_price))
        final_price = closest_offer_price
        final_seller_id = offer_prices_to_seller_ids[closest_offer_price]
        final_source = f"closest offer to {stats_source}"
        logger.info(f"ASIN {asin} [SELLER DEBUG]: Stats price was better. Adopting closest offer: Price=${final_price/100:.2f}, Seller={final_seller_id}")
    else:
        # The stats price is better, but there are NO offers. Use the stats price directly.
        final_price = best_stats_price
        final_seller_id = None
        final_source = stats_source
        logger.info(f"ASIN {asin} [SELLER DEBUG]: Stats price is best, but no offers. Using stats price: ${final_price/100:.2f}")


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