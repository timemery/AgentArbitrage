"""
This module contains functions for calculating business-related metrics
such as costs, profit, and margins based on deal data and user settings.
"""
import logging
import json
import os

# Use an absolute path to be robust against where the script is called from
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'settings.json')

def load_settings():
    """Loads the business cost settings from the settings.json file."""
    logger = logging.getLogger(__name__)
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            logger.info(f"Successfully loaded settings from {SETTINGS_FILE}")
            return settings
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Could not load or parse {SETTINGS_FILE}: {e}. Returning default values.")
        # Return a default structure if the file is missing or corrupt
        return {
            "prep_fee_per_book": 2.50,
            "estimated_shipping_per_book": 2.00,
            "estimated_tax_per_book": 15,
            "tax_exempt": False,
            "default_markup": 10
        }

def _is_valid_numeric(*args):
    """Helper function to check if all arguments are valid numbers (int or float)."""
    for arg in args:
        if not isinstance(arg, (int, float)) or arg < 0:
            return False
    return True

def calculate_total_amz_fees(peak_price, fba_fee, referral_fee_percent):
    """
    Calculates the total Amazon fees for a given peak price.
    Returns the total fee amount in dollars or '-' if inputs are invalid.
    """
    logger = logging.getLogger(__name__)
    if not _is_valid_numeric(peak_price, fba_fee, referral_fee_percent):
        logger.debug(f"Skipping AMZ fee calculation due to invalid inputs: peak_price={peak_price}, fba_fee={fba_fee}, referral_fee_percent={referral_fee_percent}")
        return '-'
    
    referral_fee_decimal = referral_fee_percent / 100.0
    referral_fee_amount = peak_price * referral_fee_decimal
    total_fees = referral_fee_amount + fba_fee
    logger.debug(f"Calculated AMZ Fees: (Peak Price {peak_price:.2f} * {referral_fee_decimal:.2f}) + FBA Fee {fba_fee:.2f} = {total_fees:.2f}")
    return total_fees

def calculate_all_in_cost(best_price, total_amz_fees, settings, shipping_included_flag):
    """
    Calculates the all-in cost for acquiring a book.
    Returns the all-in cost in dollars or '-' if inputs are invalid.
    """
    logger = logging.getLogger(__name__)
    if not _is_valid_numeric(best_price, total_amz_fees):
        logger.debug(f"Skipping All-in Cost calculation due to invalid inputs: best_price={best_price}, total_amz_fees={total_amz_fees}")
        return '-'

    prep_fee = settings.get('prep_fee_per_book', 0.0)
    tax_percent = settings.get('estimated_tax_per_book', 0)
    is_tax_exempt = settings.get('tax_exempt', False)
    estimated_shipping = settings.get('estimated_shipping_per_book', 0.0)

    logger.debug(f"Cost settings applied: Prep Fee=${prep_fee}, Tax Rate={tax_percent}%, Tax Exempt={is_tax_exempt}, Est. Shipping=${estimated_shipping}")

    tax_amount = 0.0
    if not is_tax_exempt and best_price > 0:
        tax_amount = best_price * (tax_percent / 100.0)
        logger.debug(f"Tax amount calculated: {tax_amount:.2f}")
    elif is_tax_exempt:
        logger.debug("Tax amount is 0.00 (Tax Exempt).")
    
    shipping_cost_to_add = 0.0
    if not shipping_included_flag:
        shipping_cost_to_add = estimated_shipping
        logger.debug(f"Shipping not included in Best Price, adding estimated shipping of {shipping_cost_to_add:.2f}")
    
    all_in_cost = best_price + tax_amount + prep_fee + total_amz_fees + shipping_cost_to_add
    logger.debug(f"All-in Cost: Best Price {best_price:.2f} + Tax {tax_amount:.2f} + Prep {prep_fee:.2f} + AMZ Fees {total_amz_fees:.2f} + Added Shipping {shipping_cost_to_add:.2f} = {all_in_cost:.2f}")
    return all_in_cost

def calculate_profit_and_margin(peak_price, all_in_cost):
    """
    Calculates the potential profit and profit margin.
    Returns a dictionary with 'profit' and 'margin', or '-' if inputs are invalid.
    """
    logger = logging.getLogger(__name__)
    if not _is_valid_numeric(peak_price, all_in_cost):
        logger.debug(f"Skipping Profit/Margin calculation due to invalid inputs: peak_price={peak_price}, all_in_cost={all_in_cost}")
        return {'profit': '-', 'margin': '-'}
        
    profit = peak_price - all_in_cost
    margin = (profit / peak_price) * 100 if peak_price != 0 else 0
    logger.debug(f"Profit/Margin: (Peak {peak_price:.2f} - Cost {all_in_cost:.2f}) = Profit {profit:.2f}, Margin {margin:.2f}%")
    return {'profit': profit, 'margin': margin}

def calculate_min_listing_price(all_in_cost, settings):
    """
    Calculates the minimum listing price based on the default markup.
    Returns the minimum price in dollars or '-' if inputs are invalid.
    """
    logger = logging.getLogger(__name__)
    if not _is_valid_numeric(all_in_cost):
        logger.debug(f"Skipping Min Listing Price calculation due to invalid input: all_in_cost={all_in_cost}")
        return '-'
        
    markup_percent = settings.get('default_markup', 0)
    markup_decimal = 1 + (markup_percent / 100.0)
    min_price = all_in_cost * markup_decimal
    logger.info(f"Min Listing Price Calculation: All-in Cost ({all_in_cost:.2f}) * Default Markup ({markup_percent}%) = Min Price ({min_price:.2f})")
    return min_price
