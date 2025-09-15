import logging
from .keepa_api import fetch_seller_data
from .stable_calculations import calculate_seller_quality_score
import time

logger = logging.getLogger(__name__)

# Constants
WAREHOUSE_SELLER_ID = 'A2L77EE7U53NWQ'
MIN_SELLER_QUALITY_FOR_CONDITIONAL = 0.70
AMAZON_SELLER_ID = 'ATVPDKIKX0DER'

# Condition Maps
CONDITION_MAP = {
    1: "New",
    2: "Used - Like New",
    3: "Used - Very Good",
    4: "Used - Good",
    5: "Used - Acceptable",
    6: "Collectible - Like New",
    7: "Collectible - Very Good",
    8: "Collectible - Good",
    9: "Collectible - Acceptable",
    10: "Refurbished",
    11: "Collectible"
}
CONDITIONS_REQUIRING_CHECK = {"Used - Acceptable", "Collectible", "Collectible - Like New", "Collectible - Very Good", "Collectible - Good", "Collectible - Acceptable"}

# Cache for seller data to avoid redundant API calls within a script run
seller_data_cache = {}

def _get_best_offer_analysis(product, api_key=None):
    """
    Finds the best-priced offer by identifying the cheapest valid offer and then
    applying a seller quality check only if required by the offer's condition.
    """
    asin = product.get('asin', 'N/A')
    
    # --- Step 1: Gather and price all offers ---
    all_priced_offers = []
    raw_offers = product.get('offers', [])
    if not raw_offers:
        logger.debug(f"ASIN {asin}: No offers found in product data.")
        return {'Best Price': '-', 'Seller Rank': '-', 'Seller_Quality_Score': 0.0, 'Seller ID': '-'}

    for offer in raw_offers:
        seller_id = offer.get('sellerId')
        
        # Rule: Exclude Warehouse Deals and offers without a seller ID
        if not seller_id or seller_id == WAREHOUSE_SELLER_ID:
            continue

        # Price extraction from offerCSV
        offer_csv = offer.get('offerCSV', [])
        if len(offer_csv) < 2:
            continue
        
        price = offer_csv[-2]
        shipping = offer_csv[-1]
        if shipping == -1: shipping = 0
        total_price = price + shipping
        
        if total_price > 0:
            all_priced_offers.append({
                'sellerId': seller_id,
                'price': total_price,
                'condition': CONDITION_MAP.get(offer.get('condition')),
                'isFBA': offer.get('isFBA', False)
            })

    if not all_priced_offers:
        logger.warning(f"ASIN {asin}: No valid priced offers found after initial filter.")
        return {'Best Price': '-', 'Seller Rank': '-', 'Seller_Quality_Score': 0.0, 'Seller ID': '-'}

    # --- Step 2: Sort all offers by price to find the cheapest ones first ---
    sorted_offers = sorted(all_priced_offers, key=lambda o: o['price'])

    # --- Step 3: Iterate through sorted offers and apply conditional logic ---
    best_offer_found = None
    for offer in sorted_offers:
        logger.debug(f"ASIN {asin}: Evaluating offer: Price=${offer['price']/100:.2f}, Seller={offer['sellerId']}, Condition={offer['condition']}")
        
        # Rule: If condition does NOT require a check, it's the best offer.
        if offer['condition'] not in CONDITIONS_REQUIRING_CHECK:
            logger.info(f"ASIN {asin}: Selected best offer. Price=${offer['price']/100:.2f}, Seller={offer['sellerId']}. Reason: Condition '{offer['condition']}' does not require quality check.")
            best_offer_found = offer
            break

        # Rule: If condition REQUIRES a check, perform the seller quality score logic.
        else:
            if not api_key:
                logger.debug(f"ASIN {asin}: Skipping conditional offer from seller {offer['sellerId']}. Reason: No API key provided for seller check.")
                continue

            seller_id = offer['sellerId']
            
            # Use cache for seller data
            if seller_id not in seller_data_cache:
                seller_data_cache[seller_id] = fetch_seller_data(api_key, seller_id)
            
            seller_data = seller_data_cache[seller_id]

            # A seller with no data or zero ratings is considered to have a score of 0.
            if not seller_data or seller_data.get('rating_count', 0) == 0:
                logger.debug(f"ASIN {asin}: Discarding conditional offer from seller {seller_id}. Reason: No rating data available (New Seller).")
                continue # Move to the next cheapest offer

            rating_percentage = seller_data.get('rating_percentage', 0)
            rating_count = seller_data.get('rating_count', 0)
            positive_ratings = round((rating_percentage / 100.0) * rating_count)
            seller_quality_score = calculate_seller_quality_score(positive_ratings, rating_count)

            if seller_quality_score >= MIN_SELLER_QUALITY_FOR_CONDITIONAL:
                logger.info(f"ASIN {asin}: Selected best offer. Price=${offer['price']/100:.2f}, Seller={seller_id}. Reason: Conditional offer passed quality check (Score: {seller_quality_score:.2f}).")
                best_offer_found = offer
                break # This is our best offer, stop searching
            else:
                logger.debug(f"ASIN {asin}: Discarding conditional offer from seller {seller_id}. Reason: Low quality score ({seller_quality_score:.2f}).")
                continue # Move to the next cheapest offer

    # --- Step 4: Populate final analysis from the best offer found ---
    if not best_offer_found:
        logger.warning(f"ASIN {asin}: No offer passed the filtering criteria.")
        return {'Best Price': '-', 'Seller Rank': '-', 'Seller_Quality_Score': 0.0, 'Seller ID': '-'}

    final_analysis = {}
    best_seller_id = best_offer_found['sellerId']
    
    # Fetch final seller data for the chosen offer (or use cache)
    if best_seller_id not in seller_data_cache:
        seller_data_cache[best_seller_id] = fetch_seller_data(api_key, best_seller_id)
    
    seller_data = seller_data_cache[best_seller_id]

    if seller_data:
        final_analysis['Seller Rank'] = seller_data.get('rank', '-')
        rating_percentage = seller_data.get('rating_percentage', 0)
        rating_count = seller_data.get('rating_count', 0)

        if rating_count == 0 or rating_percentage == -1:
            final_analysis['Seller_Quality_Score'] = "New Seller"
        else:
            positive_ratings = round((rating_percentage / 100.0) * rating_count)
            final_analysis['Seller_Quality_Score'] = calculate_seller_quality_score(positive_ratings, rating_count)
    else:
        final_analysis['Seller Rank'] = '-'
        final_analysis['Seller_Quality_Score'] = "New Seller" # Treat no data as a new seller

    final_analysis['Best Price'] = f"${best_offer_found['price'] / 100:.2f}"
    final_analysis['Seller ID'] = best_seller_id

    return final_analysis


def get_all_seller_info(product, api_key=None):
    """
    Public function to get all seller-related information in a single dictionary.
    This function calls the internal analysis function and returns the results
    in the format expected by the main script's row update logic.
    """
    # Simple wrapper to call the main logic. The cache is now handled internally.
    return _get_best_offer_analysis(product, api_key=api_key)
