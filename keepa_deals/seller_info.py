import logging
from .keepa_api import fetch_seller_data
from .stable_calculations import calculate_seller_quality_score

# Constants for seller IDs and quality score threshold
WAREHOUSE_SELLER_ID = 'A2L77EE7U53NWQ'
MIN_SELLER_QUALITY_FOR_CONDITIONAL = 0.7

# Condition code sets for clarity
NEW_CONDITIONS = {1}
USED_OTHER_CONDITIONS = {2, 3, 4}
USED_ACCEPTABLE_CONDITIONS = {5}
COLLECTIBLE_CONDITIONS = {6, 7, 8, 9, 10, 11}

def _get_best_offer_analysis(product, api_key=None):
    """
    Finds the best-priced offer by applying a detailed set of classification and
    filtering rules based on user requirements.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    buy_box_seller_id = product.get('buyBoxSellerId')

    cache_key = (asin, api_key)
    if not hasattr(_get_best_offer_analysis, 'cache'):
        _get_best_offer_analysis.cache = {}
    if cache_key in _get_best_offer_analysis.cache:
        logger.debug(f"ASIN {asin}: Using cached best offer analysis.")
        return _get_best_offer_analysis.cache[cache_key]

    final_analysis = {'Best Price': '-', 'Seller Rank': '-', 'Seller_Quality_Score': 0.0, 'Seller ID': '-'}

    try:
        offers = product.get('offers', [])
        if not offers:
            _get_best_offer_analysis.cache[cache_key] = final_analysis
            return final_analysis

        eligible_offers = []
        
        # Pre-calculate prices for all offers to avoid redundant calculations
        all_offers_with_price = []
        for offer in offers:
            offer_csv = offer.get('offerCSV', [])
            if len(offer_csv) < 2: continue
            price = offer_csv[-2]
            shipping = offer_csv[-1]
            if shipping == -1: shipping = 0
            total_price = price + shipping
            if total_price > 0:
                offer['calculated_price'] = total_price
                all_offers_with_price.append(offer)

        for offer in all_offers_with_price:
            seller_id = offer.get('sellerId')
            
            # Rule: Exclude Warehouse Deals and offers without a seller ID (e.g., List Price)
            if not seller_id or seller_id == WAREHOUSE_SELLER_ID:
                logger.debug(f"ASIN {asin}: Excluding offer from seller '{seller_id}'. Reason: Warehouse Deal or No Seller ID.")
                continue

            # Safely get condition code
            condition_code = offer.get('condition')

            # Rule: Include Buy Box (any grade) - Current
            is_buy_box = seller_id == buy_box_seller_id
            if is_buy_box:
                logger.debug(f"ASIN {asin}: Including offer from seller {seller_id} (Price: ${offer['calculated_price']/100:.2f}). Reason: Is Buy Box.")
                eligible_offers.append(offer)
                continue

            if condition_code is None:
                # This is the fallback logic. If an offer has no explicit condition, assume it's 'New'.
                # This is a common case for many listings.
                logger.debug(f"ASIN {asin}: No condition code for seller {seller_id}. Assuming 'New' and including.")
                eligible_offers.append(offer)
                continue

            # Rule: Include New, New FBA, New FBM - Current
            if condition_code in NEW_CONDITIONS:
                is_fba = offer.get('isFBA', False)
                is_amazon = seller_id == 'ATVPDKIKX0DER'
                # This covers New (Amazon), New FBA, and New FBM. All are included.
                logger.debug(f"ASIN {asin}: Including offer from seller {seller_id} (Price: ${offer['calculated_price']/100:.2f}). Reason: Is New (FBA: {is_fba}, Amazon: {is_amazon}).")
                eligible_offers.append(offer)
                continue
            
            # Rule: Include Used (any grade except Acceptable) - Current
            if condition_code in USED_OTHER_CONDITIONS:
                logger.debug(f"ASIN {asin}: Including offer from seller {seller_id} (Price: ${offer['calculated_price']/100:.2f}). Reason: Is Used (Good-Like New).")
                eligible_offers.append(offer)
                continue

            # Rule: Conditionally include Used, Acceptable and Collectible based on Seller Score
            is_used_acceptable = condition_code in USED_ACCEPTABLE_CONDITIONS
            is_collectible = condition_code in COLLECTIBLE_CONDITIONS

            if is_used_acceptable or is_collectible:
                if not api_key:
                    logger.debug(f"ASIN {asin}: Skipping conditional offer from seller {seller_id}. Reason: No API key for seller check.")
                    continue

                seller_data = fetch_seller_data(api_key, seller_id)
                if seller_data and seller_data.get('rating_count', 0) > 0:
                    rating_percentage = seller_data.get('rating_percentage', 0)
                    rating_count = seller_data.get('rating_count', 0)
                    positive_ratings = round((rating_percentage / 100.0) * rating_count)
                    seller_quality_score = calculate_seller_quality_score(positive_ratings, rating_count)

                    if seller_quality_score >= MIN_SELLER_QUALITY_FOR_CONDITIONAL:
                        reason = "Used Acceptable" if is_used_acceptable else "Collectible"
                        logger.debug(f"ASIN {asin}: Including conditional offer from seller {seller_id} (Price: ${offer['calculated_price']/100:.2f}). Reason: {reason} with score {seller_quality_score:.2f} >= {MIN_SELLER_QUALITY_FOR_CONDITIONAL}.")
                        eligible_offers.append(offer)
                    else:
                        logger.debug(f"ASIN {asin}: Excluding conditional offer from seller {seller_id}. Reason: Low quality score ({seller_quality_score:.2f}).")
                else:
                    logger.debug(f"ASIN {asin}: Excluding conditional offer from seller {seller_id}. Reason: No seller rating data.")
                continue
        
        if not eligible_offers:
            logger.warning(f"ASIN {asin}: No offers met the required criteria after filtering.")
            _get_best_offer_analysis.cache[cache_key] = final_analysis
            return final_analysis

        # Sort the final list of eligible offers by price and select the best one
        best_offer_found = sorted(eligible_offers, key=lambda o: o['calculated_price'])[0]

        # --- Populate final analysis from the best offer ---
        best_seller_id = best_offer_found.get('sellerId')
        seller_rank_str = '-'
        seller_quality_score_val = 0.0

        if best_seller_id and api_key:
            seller_data_to_use = fetch_seller_data(api_key, best_seller_id)
            if seller_data_to_use:
                seller_rank_str = seller_data_to_use.get('rank', '-')
                rating_percentage = seller_data_to_use.get('rating_percentage', 0)
                rating_count = seller_data_to_use.get('rating_count', 0)
                
                if rating_count == 0 or rating_percentage == -1:
                    seller_quality_score_val = "New Seller"
                else:
                    positive_ratings = round((rating_percentage / 100.0) * rating_count)
                    seller_quality_score_val = calculate_seller_quality_score(positive_ratings, rating_count)
        
        final_analysis['Best Price'] = f"${best_offer_found['calculated_price'] / 100:.2f}"
        final_analysis['Seller Rank'] = seller_rank_str
        final_analysis['Seller_Quality_Score'] = seller_quality_score_val
        final_analysis['Seller ID'] = best_seller_id
        
        log_score = seller_quality_score_val if isinstance(seller_quality_score_val, str) else f"{seller_quality_score_val:.3f}"
        logger.info(f"ASIN {asin}: Best offer selected. Price: {final_analysis['Best Price']}, Seller: {best_seller_id}, Rank: {final_analysis['Seller Rank']}, Score: {log_score}.")

        _get_best_offer_analysis.cache[cache_key] = final_analysis
        return final_analysis

    except Exception as e:
        logger.error(f"Error in _get_best_offer_analysis for ASIN {asin}: {e}", exc_info=True)
        _get_best_offer_analysis.cache[cache_key] = final_analysis
        return final_analysis

def get_all_seller_info(product, api_key=None):
    """
    Public function to get all seller-related information in a single dictionary.
    This function calls the internal analysis function and returns the results
    in the format expected by the main script's row update logic.
    """
    # The internal function now consistently returns a dictionary with the correct keys.
    analysis = _get_best_offer_analysis(product, api_key=api_key)
    return analysis
