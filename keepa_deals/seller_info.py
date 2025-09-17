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

def _get_simplified_best_price(product, api_key=None):
    """
    Finds the absolute lowest-priced offer from the live offers list,
    then fetches the quality score for that specific seller.
    This function is decoupled from any complex filtering.
    """
    asin = product.get('asin', 'N/A')
    raw_offers = product.get('offers', [])

    # Safeguard: If the raw offers list from Keepa is empty, exit immediately.
    if not raw_offers:
        logger.warning(f"ASIN {asin}: No live offers returned from Keepa. Cannot determine best price.")
        return {'Best Price': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-', 'Seller ID': '-'}

    lowest_offer = None
    lowest_price = float('inf')

    # Step 1: Find the absolute lowest-priced offer
    for offer in raw_offers:
        seller_id = offer.get('sellerId')
        if not seller_id or seller_id == WAREHOUSE_SELLER_ID:
            continue

        offer_csv = offer.get('offerCSV', [])
        # A simple offer has [timestamp, price, shipping]
        if len(offer_csv) < 2:
            continue
        
        try:
            # The price is the second-to-last element, shipping is the last.
            price = int(offer_csv[-2])
            shipping = int(offer_csv[-1])
            if shipping == -1: shipping = 0
            total_price = price + shipping

            if 0 < total_price < lowest_price:
                lowest_price = total_price
                lowest_offer = offer
        except (ValueError, IndexError):
            logger.debug(f"ASIN {asin}: Could not parse price/shipping from offerCSV for seller {seller_id}: {offer_csv}")
            continue

    if not lowest_offer:
        logger.warning(f"ASIN {asin}: No valid, priced offers found in the raw offer list.")
        return {'Best Price': '-', 'Seller Rank': '-', 'Seller_Quality_Score': '-', 'Seller ID': '-'}

    # Step 2: We have the lowest offer. Now get its seller's data.
    best_seller_id = lowest_offer.get('sellerId')
    final_analysis = {
        'Best Price': f"${lowest_price / 100:.2f}",
        'Seller ID': best_seller_id,
        'Seller Rank': '-',
        'Seller_Quality_Score': '-'
    }
    
    logger.info(f"ASIN {asin}: Found lowest price offer: ${lowest_price/100:.2f} from Seller ID: {best_seller_id}")

    if not api_key or not best_seller_id:
        logger.warning(f"ASIN {asin}: Cannot fetch seller score. No API key or seller ID.")
        return final_analysis

    # Step 3: Fetch seller data and calculate score for THAT seller
    if best_seller_id not in seller_data_cache:
        seller_data_cache[best_seller_id] = fetch_seller_data(api_key, best_seller_id)
    
    seller_data = seller_data_cache.get(best_seller_id)

    if seller_data:
        # This part of the logic is now greatly simplified
        # It gets the data for the specific seller of the lowest-priced item
        seller_ratings = seller_data.get(best_seller_id, {})
        rating_count = seller_ratings.get('currentRatingCount', 0)
        
        if rating_count > 0:
            final_analysis['Seller Rank'] = rating_count
            rating_percentage = seller_ratings.get('currentRating', 0)
            positive_ratings = round((rating_percentage / 100.0) * rating_count)
            score = calculate_seller_quality_score(positive_ratings, rating_count)
            final_analysis['Seller_Quality_Score'] = f"{score:.2f}/10" # Format as a score out of 10
        else:
            final_analysis['Seller_Quality_Score'] = "New Seller"
    else:
        logger.warning(f"ASIN {asin}: No seller data returned for the best price seller ID: {best_seller_id}")
        final_analysis['Seller_Quality_Score'] = "New Seller"

    return final_analysis

def get_all_seller_info(product, api_key=None):
    """
    Public function to get all seller-related information in a single dictionary.
    This now calls the simplified best price logic.
    """
    return _get_simplified_best_price(product, api_key=api_key)
