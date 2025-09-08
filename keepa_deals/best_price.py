import logging
# updated manually below
def _get_best_offer_analysis(product):
    """
    Analyzes all offers for a product to find the best one based on specific criteria.
    This function is a helper and its result is cached on the product object to avoid re-computation.
    
    The criteria are:
    - Considers all conditions ('New', 'Like New', 'Very Good', 'Good', 'Acceptable').
    - Finds the offer with the absolute lowest price (including shipping).
    
    Returns a dictionary containing the best price. Seller rank is currently not available.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    # This is a shared dictionary to cache results for a single run.
    # It's a simple way to avoid re-calculating for the same product.
    if not hasattr(_get_best_offer_analysis, 'cache'):
        _get_best_offer_analysis.cache = {}
    
    if asin in _get_best_offer_analysis.cache:
        logger.debug(f"ASIN {asin}: Using cached best offer analysis.")
        return _get_best_offer_analysis.cache[asin]

    try:
        offers = product.get('offers', [])
        if not offers:
            logger.debug(f"ASIN {asin}: No 'offers' array in product data, cannot determine Best Price.")
            analysis = {'best_price': '-', 'seller_rank': '-'}
            _get_best_offer_analysis.cache[asin] = analysis
            return analysis

        valid_offers_with_prices = []
        for offer in offers:
            offer_csv = offer.get('offerCSV', [])
            # The offerCSV is a flat list: [timestamp, price, shipping, ...]
            # We need the last price and shipping, which are the last two elements.
            if len(offer_csv) >= 2:
                price = offer_csv[-2]
                shipping = offer_csv[-1]
                
                # A shipping cost of -1 indicates it's included in the price or free.
                if shipping == -1:
                    shipping = 0
                
                total_price = price + shipping
                
                if total_price > 0:
                    # Add the calculated price to the offer object for sorting later
                    offer['calculated_price'] = total_price
                    valid_offers_with_prices.append(offer)
            else:
                logger.debug(f"ASIN {asin}: Skipping offer due to empty or incomplete offerCSV: {offer_csv}")


        if not valid_offers_with_prices:
            logger.info(f"ASIN {asin}: No offers with valid prices found.")
            analysis = {'best_price': '-', 'seller_rank': '-'}
            _get_best_offer_analysis.cache[asin] = analysis
            return analysis

        # Find the single best offer (the one with the minimum calculated price)
        best_offer = min(valid_offers_with_prices, key=lambda o: o['calculated_price'])
        
        best_price_cents = best_offer['calculated_price']
        
        # Seller rank is not available in the offer object, so we return '-'
        analysis = {
            'best_price': f"${best_price_cents / 100:.2f}",
            'seller_rank': "-" 
        }
        
        logger.info(f"ASIN {asin}: Best offer found. Price: {analysis['best_price']}.")
        
        # Cache the result
        _get_best_offer_analysis.cache[asin] = analysis
        return analysis

    except Exception as e:
        logger.error(f"Error in _get_best_offer_analysis for ASIN {asin}: {e}", exc_info=True)
        analysis = {'best_price': '-', 'seller_rank': '-'}
        _get_best_offer_analysis.cache[asin] = analysis
        return analysis
# updated manually above
def get_best_price(product):
    """
    Wrapper function to get the 'Best Price' from the analysis.
    """
    analysis = _get_best_offer_analysis(product)
    return {'Best Price': analysis['best_price']}

def get_seller_rank(product):
    """
    Wrapper function to get the 'Seller Rank' of the seller who has the best price.
    """
    analysis = _get_best_offer_analysis(product)
    return {'Seller Rank': analysis['seller_rank']}
