import logging

def _get_best_offer_analysis(product):
    """
    Analyzes all offers for a product to find the best one based on specific criteria.
    This function is a helper and its result is cached on the product object to avoid re-computation.
    
    The criteria are:
    - Excludes 'Acceptable' condition unless the seller has a rating of 95% or higher.
    - Considers all other used conditions ('New', 'Like New', 'Very Good', 'Good').
    - Finds the offer with the absolute lowest price among the valid offers.
    
    Returns a dictionary containing the best price and the corresponding seller's rank.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    # Check if the result is already cached
    if hasattr(product, '_best_offer_cache'):
        logger.debug(f"ASIN {asin}: Using cached best offer analysis.")
        return product._best_offer_cache

    try:
        offers = product.get('offers', [])
        
        # --- JULES DEBUGGING ---
        if offers and not hasattr(logging, '_logged_offers'):
            logger.info(f"JULES DEBUG: Received offers for ASIN {asin}. Full offers list: {offers}")
            logging._logged_offers = True # Log only once
        # --- END JULES DEBUGGING ---

        if not offers:
            logger.debug(f"ASIN {asin}: No offers found, cannot determine Best Price.")
            analysis = {'best_price': '-', 'seller_rank': '-'}
            product._best_offer_cache = analysis
            return analysis

        valid_offers = []
        for offer in offers:
            price = offer.get('price')
            if price is None or price <= 0:
                continue

            condition = offer.get('condition')
            seller_rating = offer.get('sellerRating', -1)
            
            # Condition mapping from Keepa's integer codes
            # 1: New, 2: Used - Like New, 3: Used - Very Good, 4: Used - Good, 5: Used - Acceptable
            if condition == 5: # Used - Acceptable
                if seller_rating >= 95:
                    valid_offers.append(offer)
                    logger.debug(f"ASIN {asin}: Including 'Acceptable' offer at ${price/100:.2f} from seller with rating {seller_rating}%.")
                else:
                    logger.debug(f"ASIN {asin}: Excluding 'Acceptable' offer at ${price/100:.2f} due to low/no seller rating ({seller_rating}%).")
            elif condition in [1, 2, 3, 4]:
                valid_offers.append(offer)

        if not valid_offers:
            logger.info(f"ASIN {asin}: No offers met the criteria for Best Price.")
            analysis = {'best_price': '-', 'seller_rank': '-'}
            product._best_offer_cache = analysis
            return analysis

        # Find the single best offer (the one with the minimum price)
        best_offer = min(valid_offers, key=lambda o: o['price'])
        
        best_price_cents = best_offer['price']
        best_offer_seller_rank = best_offer.get('sellerRating', -1)

        analysis = {
            'best_price': f"${best_price_cents / 100:.2f}",
            'seller_rank': f"{best_offer_seller_rank}%" if best_offer_seller_rank != -1 else "-"
        }
        
        logger.info(f"ASIN {asin}: Best offer found. Price: {analysis['best_price']}, Seller Rank: {analysis['seller_rank']}.")
        
        # Cache the result on the product object
        product._best_offer_cache = analysis
        return analysis

    except Exception as e:
        logger.error(f"Error in _get_best_offer_analysis for ASIN {asin}: {e}", exc_info=True)
        analysis = {'best_price': '-', 'seller_rank': '-'}
        product._best_offer_cache = analysis
        return analysis

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
