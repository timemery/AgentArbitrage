import logging
from .keepa_api import fetch_seller_data
from .stable_calculations import calculate_seller_quality_score

# updated manually below
def _get_best_offer_analysis(product, api_key=None):
    """
    Analyzes all offers for a product to find the best one based on specific criteria.
    This function is a helper and its result is cached on the product object to avoid re-computation.
    
    The criteria are:
    - Considers all conditions ('New', 'Like New', 'Very Good', 'Good', 'Acceptable').
    - Finds the offer with the absolute lowest price (including shipping).
    
    Returns a dictionary containing the best price and seller rank.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    # This is a shared dictionary to cache results for a single run.
    if not hasattr(_get_best_offer_analysis, 'cache'):
        _get_best_offer_analysis.cache = {}
    
    if asin in _get_best_offer_analysis.cache:
        logger.debug(f"ASIN {asin}: Using cached best offer analysis.")
        return _get_best_offer_analysis.cache[asin]

    try:
        offers = product.get('offers', [])
        if not offers:
            logger.debug(f"ASIN {asin}: No 'offers' array in product data, cannot determine Best Price.")
            analysis = {'best_price': '-', 'seller_rank': '-', 'seller_quality_score': 0.0}
            _get_best_offer_analysis.cache[asin] = analysis
            return analysis

        valid_offers_with_prices = []
        for offer in offers:
            offer_csv = offer.get('offerCSV', [])
            if len(offer_csv) >= 2:
                price = offer_csv[-2]
                shipping = offer_csv[-1]
                
                if shipping == -1:
                    shipping = 0
                
                total_price = price + shipping
                
                if total_price > 0:
                    offer['calculated_price'] = total_price
                    valid_offers_with_prices.append(offer)
            else:
                logger.debug(f"ASIN {asin}: Skipping offer due to empty or incomplete offerCSV: {offer_csv}")

        if not valid_offers_with_prices:
            logger.info(f"ASIN {asin}: No offers with valid prices found.")
            analysis = {'best_price': '-', 'seller_rank': '-', 'seller_quality_score': 0.0}
            _get_best_offer_analysis.cache[asin] = analysis
            return analysis

        best_offer = min(valid_offers_with_prices, key=lambda o: o['calculated_price'])
        best_price_cents = best_offer['calculated_price']
        
        seller_rank_str = "-"
        seller_quality_score = 0.0
        seller_id = best_offer.get('sellerId')
        if seller_id and api_key:
            seller_data = fetch_seller_data(api_key, seller_id)
            if seller_data:
                seller_rank_str = seller_data.get('rank', '-')
                rating_percentage = seller_data.get('rating_percentage', 0)
                rating_count = seller_data.get('rating_count', 0)
                if rating_count > 0:
                    positive_ratings = round((rating_percentage / 100.0) * rating_count)
                    seller_quality_score = calculate_seller_quality_score(positive_ratings, rating_count)

        analysis = {
            'best_price': f"${best_price_cents / 100:.2f}",
            'seller_rank': seller_rank_str,
            'seller_quality_score': seller_quality_score
        }
        
        logger.info(f"ASIN {asin}: Best offer found. Price: {analysis['best_price']}, Seller Rank: {analysis['seller_rank']}.")
        
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
