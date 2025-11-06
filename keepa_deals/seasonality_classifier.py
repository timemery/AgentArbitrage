# Restore Dashboard Functionality
import re
import httpx
import json
import logging
from .xai_token_manager import XaiTokenManager
from .xai_cache import XaiCache

# Configure logging
logger = logging.getLogger(__name__)

# Initialize cache and token manager at the module level to act as singletons
xai_cache = XaiCache()
xai_token_manager = XaiTokenManager()

SEASON_CLASSIFICATIONS = [
    "Textbook (Summer)", "Textbook (Winter)", "High School AP Textbooks",
    "Law School", "Nursing School", "Medical School", "Community College",
    "Gardening", "Grilling/BBQ", "Christmas", "New Year/Fitness",
    "Tax Prep", "Travel", "Halloween", "Thanksgiving", "Romance/Valentine's Day",
    "Year-round"
]

def _query_xai_for_seasonality(title, categories_sub, manufacturer, peak_season_str, trough_season_str, api_key):
    """
    Queries the XAI API to classify seasonality, now with caching and token management.
    """
    if not api_key:
        logger.warning("XAI API key is not provided. Skipping LLM classification.")
        return "Year-round"

    # 1. Create a unique cache key
    cache_key = f"seasonality:{title}|{categories_sub}|{manufacturer}"

    # 2. Check cache first
    cached_result = xai_cache.get(cache_key)
    if cached_result:
        logger.info(f"XAI Cache HIT for seasonality. Found classification '{cached_result}' for title '{title}'.")
        return cached_result

    # 3. If not in cache, check for permission to make a call
    if not xai_token_manager.request_permission():
        logger.warning(f"XAI daily limit reached. Cannot classify '{title}'. Defaulting to Year-round.")
        return "Year-round"

    # 4. If permission granted, proceed with the API call
    prompt = f"""
    Based on the following book details and historical sales data, choose the single most likely sales season from the provided list.
    Respond with ONLY the name of the season from the list.

    **Book Details:**
    - **Title:** "{title}"
    - **Category:** "{categories_sub}"
    - **Publisher:** "{manufacturer}"

    **Sales Data Insights:**
    - **Inferred Peak Price Month:** "{peak_season_str if peak_season_str and peak_season_str != '-' else 'N/A'}"
    - **Inferred Trough Price Month:** "{trough_season_str if trough_season_str and trough_season_str != '-' else 'N/A'}"

    **Season List:**
    {', '.join(SEASON_CLASSIFICATIONS)}
    """

    logger.info(f"XAI Seasonality Request for ASIN '{title}' (Cache MISS):")
    logger.info(f"  - Peak: {peak_season_str}, Trough: {trough_season_str}")

    payload = {
        "messages": [
            {"role": "system", "content": "You are a book classification expert. Your task is to select the most appropriate seasonal category for a book from a given list."},
            {"role": "user", "content": prompt}
        ],
        "model": "grok-4-fast", # Switched to the faster, cheaper model
        "temperature": 0.1,
        "max_tokens": 50
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status() # This will now handle 429 errors as failures
            data = response.json()
            llm_choice = data['choices'][0]['message']['content'].strip()

            if llm_choice in SEASON_CLASSIFICATIONS:
                logger.info(f"LLM classified '{title}' as: {llm_choice}")
                xai_cache.set(cache_key, llm_choice) # 5. Cache the successful result
                return llm_choice
            else:
                logger.warning(f"LLM returned an invalid classification: '{llm_choice}'. Defaulting to Year-round.")
                return "Year-round"

    except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"XAI API request failed for title '{title}': {e}")
        # We no longer retry here; the token manager prevents us from hitting 429s.
        return "Year-round"


def classify_seasonality(title, categories_sub, manufacturer, peak_season_str, trough_season_str, xai_api_key=None):
    """
    Classifies a book's seasonality based on heuristics and an XAI model,
    now enriched with inferred sales data.

    Args:
        title (str): The title of the book.
        categories_sub (str): The sub-category string.
        manufacturer (str): The manufacturer/publisher.
        peak_season_str (str): The inferred month of peak prices (e.g., "Jan").
        trough_season_str (str): The inferred month of trough prices (e.g., "Jul").
        xai_api_key (str, optional): The API key for the XAI service.

    Returns:
        str: The classified season.
    """
    if not title: title = ""
    if not categories_sub: categories_sub = ""
    if not manufacturer: manufacturer = ""

    title_lower = title.lower()
    cat_lower = categories_sub.lower()
    mfr_lower = manufacturer.lower()

    # --- Textbook Classifications ---
    textbook_publishers = ['cengage', 'mcgraw-hill', 'pearson', 'wiley', 'macmillan', 'sage']
    is_textbook_publisher = any(pub in mfr_lower for pub in textbook_publishers)

    if "ap" in title_lower and ("high school" in cat_lower or is_textbook_publisher):
        return "High School AP Textbooks"
    if "college" in title_lower or "university" in title_lower or is_textbook_publisher:
        if "summer" in title_lower:
            return "Textbook (Summer)"
        if "winter" in title_lower:
            return "Textbook (Winter)"
        # General textbook seasons if not specified
        return "Textbook (Summer)" # Defaulting to most common

    # --- Niche Semesters ---
    if "law school" in cat_lower or "bar exam" in title_lower:
        return "Law School"
    if "nursing" in cat_lower or "nclex" in title_lower:
        return "Nursing School"
    if "medical school" in cat_lower or "mcat" in title_lower:
        return "Medical School"
    if "community college" in cat_lower:
        return "Community College"

    # --- General Seasonal ---
    if "gardening" in cat_lower or "gardening" in title_lower:
        return "Gardening"
    if "grilling" in cat_lower or "bbq" in title_lower or "barbecue" in title_lower:
        return "Grilling/BBQ"
    if "christmas" in title_lower or "holiday" in title_lower and "gift" in title_lower:
        return "Christmas"
    if "new year" in title_lower or "fitness" in title_lower or "diet" in title_lower or "self-help" in title_lower and "resolution" in title_lower:
        return "New Year/Fitness"
    if "tax" in title_lower and ("prep" in title_lower or "guide" in title_lower):
        return "Tax Prep"
    if "travel" in cat_lower or "travel" in title_lower:
        return "Travel"
    if "halloween" in title_lower:
        return "Halloween"
    if "thanksgiving" in title_lower:
        return "Thanksgiving"
    if "valentine" in title_lower or "romance" in cat_lower:
        return "Romance/Valentine's Day"

    # --- Fallback to LLM with enriched data ---
    # Heuristics resulted in "Year-round", so we query the AI with the date data for a more refined answer.
    logger.info(f"Heuristics resulted in 'Year-round' for '{title}'. Querying XAI with sales data for refinement.")

    llm_result = _query_xai_for_seasonality(
        title, categories_sub, manufacturer, peak_season_str, trough_season_str, xai_api_key
    )

    # The AI's response is now the final answer for this logic path.
    return llm_result


def get_sells_period(detailed_season):
    """
    Maps a detailed season classification from the 'Detailed_Seasonality' column
    to a specific selling period string for the 'Sells' column.

    Args:
        detailed_season (str): The detailed season name.

    Returns:
        str: A string representing the peak selling period (e.g., "Nov-Dec").
             Returns "All Year" if no specific period is applicable.
    """
    period_map = {
        "Textbook (Summer)": "Jul - Sep",
        "Textbook (Winter)": "Jan - Feb",
        "High School AP Textbooks": "Jul - Sep",
        "Law School": "Oct",
        "Nursing School": "Mar - Apr",
        "Medical School": "Aug - Sep",
        "Community College": "Sep - Oct & Jan - Feb",
        "Gardening": "Mar - Apr",
        "Grilling/BBQ": "May - Jun",
        "Christmas": "Nov - Dec",
        "New Year/Fitness": "Jan",
        "Tax Prep": "Jan - Apr",
        "Travel": "May - Aug",
        "Halloween": "Sep - Oct",
        "Thanksgiving": "Nov",
        "Romance/Valentine's Day": "Feb",
        "Year-round": "All Year"
    }
    return period_map.get(detailed_season, "All Year")