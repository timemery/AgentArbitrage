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

def calculate_all_in_cost(now_price, list_at_price, fba_fee, referral_fee_percent, settings, shipping_included_flag):
    """
    Calculates the all-in cost for acquiring and selling a book.
    The Referral Fee is now correctly calculated based on the 'List at' price.
    """
    logger = logging.getLogger(__name__)

    # --- Validate Inputs ---
    if not all(_is_valid_numeric(val) for val in [now_price, fba_fee, referral_fee_percent]):
        logger.info(f"Skipping All-in Cost: Invalid base numeric inputs. now_price={now_price}, fba_fee={fba_fee}, ref_fee_pct={referral_fee_percent}")
        return '-'
    
    # list_at_price can be invalid (e.g., 'Too New'), which is acceptable
    is_list_at_price_valid = _is_valid_numeric(list_at_price)

    # --- Calculate Amazon Fees ---
    referral_fee_amount = 0.0
    if is_list_at_price_valid:
        referral_fee_decimal = referral_fee_percent / 100.0
        referral_fee_amount = list_at_price * referral_fee_decimal
        logger.debug(f"Referral Fee: List At Price ({list_at_price:.2f}) * {referral_fee_decimal:.2f} = {referral_fee_amount:.2f}")
    else:
        logger.debug(f"Referral Fee: Could not be calculated as List At Price is invalid ({list_at_price}).")

    total_amz_fees = referral_fee_amount + fba_fee
    logger.debug(f"Total AMZ Fees: Referral Fee ({referral_fee_amount:.2f}) + FBA Fee ({fba_fee:.2f}) = {total_amz_fees:.2f}")

    # --- Load User Settings ---
    prep_fee = settings.get('prep_fee_per_book', 0.0)
    tax_percent = settings.get('estimated_tax_per_book', 0)
    is_tax_exempt = settings.get('tax_exempt', False)
    estimated_shipping = settings.get('estimated_shipping_per_book', 0.0)
    logger.info(f"Cost settings: Prep=${prep_fee}, Tax={tax_percent}%, Exempt={is_tax_exempt}, Est. Ship=${estimated_shipping}")

    # --- Calculate Other Costs ---
    tax_amount = 0.0
    if not is_tax_exempt and now_price > 0:
        tax_amount = now_price * (tax_percent / 100.0)
    
    shipping_cost_to_add = estimated_shipping if not shipping_included_flag else 0.0
    
    # --- Final Calculation ---
    all_in_cost = now_price + tax_amount + prep_fee + total_amz_fees + shipping_cost_to_add
    logger.info(
        f"All-in Cost Breakdown: "
        f"Now Price ({now_price:.2f}) + "
        f"Tax ({tax_amount:.2f}) + "
        f"Prep ({prep_fee:.2f}) + "
        f"AMZ Fees ({total_amz_fees:.2f}) + "
        f"Added Ship ({shipping_cost_to_add:.2f}) = "
        f"{all_in_cost:.2f}"
    )
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
    Calculates the minimum listing price required to achieve the user's default markup.
    This value is intended for use as a floor price in repricing software.
    Formula: All-in Cost / (1 - Default Markup %)
    """
    logger = logging.getLogger(__name__)
    if not _is_valid_numeric(all_in_cost):
        logger.debug(f"Skipping Min Listing Price calculation due to invalid input: all_in_cost={all_in_cost}")
        return '-'
        
    markup_percent = settings.get('default_markup', 10) # Default to 10% if not set
    if markup_percent >= 100:
        logger.warning(f"Default markup is {markup_percent}%, which is >= 100%. This is not allowed. Capping at 99%.")
        markup_percent = 99

    # Convert markup to the correct decimal for the formula
    # e.g., 10% markup means the cost is 90% of the price. 1 - 0.10 = 0.90
    denominator = 1 - (markup_percent / 100.0)

    if denominator <= 0:
        logger.error(f"Cannot calculate min list price with markup {markup_percent}%, as denominator is {denominator}")
        return '-'

    min_price = all_in_cost / denominator
    logger.info(
        f"Min Listing Price Calculation: "
        f"All-in Cost ({all_in_cost:.2f}) / (1 - Markup {markup_percent}%) = "
        f"Min Price ({min_price:.2f})"
    )
    return min_price
