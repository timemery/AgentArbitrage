import logging
from .keepa_api import fetch_seller_data_batch
from .stable_calculations import calculate_seller_quality_score

MIN_SELLER_QUALITY_FOR_ACCEPTABLE = 0.70

def _get_best_offer_analysis(product, api_key=None):
    """
    Analyzes all offers for a product to find the best one based on specific criteria.
    Refactored to use batch seller data fetching to avoid rate limiting.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    if not hasattr(_get_best_offer_analysis, 'cache'):
        _get_best_offer_analysis.cache = {}
    
    if asin in _get_best_offer_analysis.cache:
        logger.debug(f"ASIN {asin}: Using cached best offer analysis.")
        return _get_best_offer_analysis.cache[asin]

    try:
        offers = product.get('offers', [])
        if not offers:
            analysis = {'best_price': '-', 'seller_rank': '-', 'seller_quality_score': 0.0}
            _get_best_offer_analysis.cache[asin] = analysis
            return analysis

        # --- Step 1: Batch fetch all seller data ---
        all_seller_ids = {offer.get('sellerId') for offer in offers if offer.get('sellerId')}
        all_seller_data = {}
        if all_seller_ids and api_key:
            all_seller_data = fetch_seller_data_batch(api_key, list(all_seller_ids))
        
        # --- Step 2: Pre-calculate all seller quality scores ---
        seller_quality_scores = {}
        for seller_id, seller_data in all_seller_data.items():
            score = 0.0
            if seller_data:
                rating_percentage = seller_data.get('rating_percentage', 0)
                rating_count = seller_data.get('rating_count', 0)
                if rating_count > 0:
                    positive_ratings = round((rating_percentage / 100.0) * rating_count)
                    score = calculate_seller_quality_score(positive_ratings, rating_count)
            seller_quality_scores[seller_id] = score

        # --- Step 3: Filter offers and calculate prices ---
        valid_offers_with_prices = []
        for offer in offers:
            offer_csv = offer.get('offerCSV', [])
            if len(offer_csv) < 2:
                logger.debug(f"ASIN {asin}: Skipping offer due to incomplete offerCSV (len < 2): {offer_csv}")
                continue

            # Filter by seller quality if applicable
            condition = offer_csv[1] if len(offer_csv) >= 4 else None
            if condition in {5, 6, 7, 8, 9, 10, 11}: # Acceptable or Collectible
                seller_id = offer.get('sellerId')
                if seller_id:
                    seller_score = seller_quality_scores.get(seller_id, 0.0)
                    if seller_score < MIN_SELLER_QUALITY_FOR_ACCEPTABLE:
                        logger.info(f"ASIN {asin}: Excluding offer from seller {seller_id} with quality score {seller_score:.2f} below threshold.")
                        continue

            # Calculate total price
            price = offer_csv[-2]
            shipping = offer_csv[-1]
            if shipping == -1: shipping = 0
            total_price = price + shipping
            
            if total_price > 0:
                offer['calculated_price'] = total_price
                valid_offers_with_prices.append(offer)

        if not valid_offers_with_prices:
            analysis = {'best_price': '-', 'seller_rank': '-', 'seller_quality_score': 0.0}
            _get_best_offer_analysis.cache[asin] = analysis
            return analysis

        # --- Step 4: Find the best offer and construct the result ---
        best_offer = min(valid_offers_with_prices, key=lambda o: o['calculated_price'])
        best_price_cents = best_offer['calculated_price']
        
        seller_rank_str = "-"
        seller_quality_score = 0.0
        best_seller_id = best_offer.get('sellerId')

        if best_seller_id:
            seller_quality_score = seller_quality_scores.get(best_seller_id, 0.0)
            seller_data = all_seller_data.get(best_seller_id)
            if seller_data:
                seller_rank_str = seller_data.get('rank', '-')
        
        analysis = {
            'best_price': f"${best_price_cents / 100:.2f}",
            'seller_rank': seller_rank_str,
            'seller_quality_score': seller_quality_score
        }
        
        logger.info(f"ASIN {asin}: Best offer analysis complete. Price: {analysis['best_price']}, Seller Rank: {analysis['seller_rank']}, Score: {analysis['seller_quality_score']:.3f}.")
        
        # Only cache the result if the API key was provided, to ensure a full analysis was done.
        # This prevents caching an incomplete result (without seller data) that would block subsequent calls.
        if api_key:
            _get_best_offer_analysis.cache[asin] = analysis
        
        return analysis

    except Exception as e:
        logger.error(f"Error in _get_best_offer_analysis for ASIN {asin}: {e}", exc_info=True)
        analysis = {'best_price': '-', 'seller_rank': '-', 'seller_quality_score': 0.0}
        _get_best_offer_analysis.cache[asin] = analysis
        return analysis
# updated manually above
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

def get_seller_quality_score(product, api_key=None):
    """
    Wrapper function to get the 'Seller Quality Score' from the analysis.
    """
    analysis = _get_best_offer_analysis(product, api_key=api_key)
    return {'Seller_Quality_Score': analysis['seller_quality_score']}
