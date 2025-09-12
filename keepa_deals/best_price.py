import logging
from .keepa_api import fetch_seller_data
from .stable_calculations import calculate_seller_quality_score

MIN_SELLER_QUALITY_FOR_ACCEPTABLE = 0.70

def _get_best_offer_analysis(product, api_key=None):
    """
    Finds the best-priced offer that meets the quality criteria.
    The seller quality score is ONLY used as a filter for 'Acceptable' condition items.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    if not hasattr(_get_best_offer_analysis, 'cache'):
        _get_best_offer_analysis.cache = {}
    if asin in _get_best_offer_analysis.cache:
        logger.debug(f"ASIN {asin}: Using cached best offer analysis.")
        return _get_best_offer_analysis.cache[asin]

    final_analysis = {'best_price': '-', 'seller_rank': '-', 'seller_quality_score': 0.0, 'seller_id': '-'}

    try:
        offers = product.get('offers', [])
        if not offers:
            _get_best_offer_analysis.cache[asin] = final_analysis
            return final_analysis

        valid_offers = []
        for offer in offers:
            offer_csv = offer.get('offerCSV', [])
            if len(offer_csv) < 2: continue
            price = offer_csv[-2]
            shipping = offer_csv[-1]
            if shipping == -1: shipping = 0
            total_price = price + shipping
            if total_price > 0:
                offer['calculated_price'] = total_price
                valid_offers.append(offer)

        if not valid_offers:
            _get_best_offer_analysis.cache[asin] = final_analysis
            return final_analysis
        
        sorted_offers = sorted(valid_offers, key=lambda o: o['calculated_price'])

        best_offer_found = None
        best_offer_seller_data = None # Variable to store seller data if fetched during the loop
        
        for offer in sorted_offers:
            condition_code = offer['offerCSV'][1] if len(offer['offerCSV']) >= 4 else None
            is_acceptable_condition = condition_code in {5, 6, 7, 8, 9, 10, 11}

            # If the offer is 'Acceptable', we must check the seller's quality.
            if is_acceptable_condition:
                seller_id = offer.get('sellerId')
                if not seller_id or not api_key:
                    logger.debug(f"ASIN {asin}: Skipping 'Acceptable' offer, no sellerId or api_key.")
                    continue

                seller_data = fetch_seller_data(api_key, seller_id)
                best_offer_seller_data = seller_data # Store the data
                
                # If seller data is available, calculate score. Otherwise, treat as passing.
                if seller_data and seller_data.get('rating_count', 0) > 0:
                    rating_percentage = seller_data.get('rating_percentage', 0)
                    rating_count = seller_data.get('rating_count', 0)
                    positive_ratings = round((rating_percentage / 100.0) * rating_count)
                    seller_quality_score = calculate_seller_quality_score(positive_ratings, rating_count)
                    
                    if seller_quality_score < MIN_SELLER_QUALITY_FOR_ACCEPTABLE:
                        logger.info(f"ASIN {asin}: Skipping 'Acceptable' offer from seller {seller_id}. Price: ${offer['calculated_price']/100:.2f}. Reason: Low quality score ({seller_quality_score:.2f}).")
                        continue # Quality too low, skip to next cheapest offer.
            
            # If we are here, the offer is either not 'Acceptable' or it is and passed the quality check.
            # This is our best offer.
            best_offer_found = offer
            break

        # --- Step 3: Construct the final result based on the best offer found ---
        if best_offer_found:
            # Now, fetch seller data for the selected offer if we don't have it already.
            best_seller_id = best_offer_found.get('sellerId')
            seller_rank_str = '-'
            seller_quality_score = 0.0

            # Use already fetched seller data if available, otherwise fetch it now.
            seller_data_to_use = best_offer_seller_data
            if not seller_data_to_use and best_seller_id and api_key:
                seller_data_to_use = fetch_seller_data(api_key, best_seller_id)

            if seller_data_to_use:
                seller_rank_str = seller_data_to_use.get('rank', '-')
                rating_percentage = seller_data_to_use.get('rating_percentage', 0)
                rating_count = seller_data_to_use.get('rating_count', 0)
                
                if rating_count == 0 or rating_percentage == -1:
                    seller_quality_score = "New Seller"
                else:
                    positive_ratings = round((rating_percentage / 100.0) * rating_count)
                    seller_quality_score = calculate_seller_quality_score(positive_ratings, rating_count)

            final_analysis = {
                'best_price': f"${best_offer_found['calculated_price'] / 100:.2f}",
                'seller_rank': seller_rank_str,
                'seller_quality_score': seller_quality_score,
                'seller_id': best_seller_id
            }
            log_score = seller_quality_score if isinstance(seller_quality_score, str) else f"{seller_quality_score:.3f}"
            logger.info(f"ASIN {asin}: Best offer selected. Price: {final_analysis['best_price']}, Seller: {best_seller_id}, Rank: {final_analysis['seller_rank']}, Score: {log_score}.")
        else:
            logger.warning(f"ASIN {asin}: No suitable offer found. All 'Acceptable' offers checked were from sellers with low quality scores.")

        _get_best_offer_analysis.cache[asin] = final_analysis
        return final_analysis

    except Exception as e:
        logger.error(f"Error in _get_best_offer_analysis for ASIN {asin}: {e}", exc_info=True)
        _get_best_offer_analysis.cache[asin] = final_analysis
        return final_analysis

def get_best_price(product, api_key=None):
    """
    Wrapper function to get the 'Best Price' from the analysis.
    """
    analysis = _get_best_offer_analysis(product, api_key=api_key)
    return {'Best Price': analysis['best_price']}

def get_seller_rank(product, api_key=None):
    """
    Wrapper function to get the 'Seller Rank' of the seller who has the best price.
    """
    analysis = _get_best_offer_analysis(product, api_key=api_key)
    return {'Seller Rank': analysis['seller_rank']}

def get_seller_id(product, api_key=None):
    """
    Wrapper function to get the 'Seller ID' of the seller who has the best price.
    """
    analysis = _get_best_offer_analysis(product, api_key=api_key)
    return {'Seller ID': analysis['seller_id']}

def get_seller_quality_score(product, api_key=None):
    """
    Wrapper function to get the 'Seller Quality Score' from the analysis.
    """
    analysis = _get_best_offer_analysis(product, api_key=api_key)
    return {'Seller_Quality_Score': analysis['seller_quality_score']}
