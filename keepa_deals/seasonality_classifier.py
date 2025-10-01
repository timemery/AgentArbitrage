import re
import httpx
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)

SEASON_CLASSIFICATIONS = [
    "Textbook (Summer)", "Textbook (Winter)", "High School AP Textbooks",
    "Law School", "Nursing School", "Medical School", "Community College",
    "Gardening", "Grilling/BBQ", "Christmas", "New Year/Fitness",
    "Tax Prep", "Travel", "Halloween", "Thanksgiving", "Romance/Valentine's Day",
    "Year-round"
]

def _query_xai_for_seasonality(title, categories_sub, manufacturer, api_key):
    """
    Queries the XAI API to classify seasonality as a fallback.
    """
    if not api_key:
        logger.warning("XAI API key is not provided. Skipping LLM classification.")
        return "Year-round"

    prompt = f"""
    Based on the following book details, choose the single most likely sales season from the provided list.
    Respond with ONLY the name of the season from the list.

    **Book Details:**
    - **Title:** "{title}"
    - **Category:** "{categories_sub}"
    - **Publisher:** "{manufacturer}"

    **Season List:**
    {', '.join(SEASON_CLASSIFICATIONS)}
    """

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a book classification expert. Your task is to select the most appropriate seasonal category for a book from a given list."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "model": "grok-4-latest",
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
            response.raise_for_status()
            data = response.json()
            llm_choice = data['choices'][0]['message']['content'].strip()

            # Validate the response is one of the allowed classifications
            if llm_choice in SEASON_CLASSIFICATIONS:
                logger.info(f"LLM classified '{title}' as: {llm_choice}")
                return llm_choice
            else:
                logger.warning(f"LLM returned an invalid classification: '{llm_choice}'. Defaulting to Year-round.")
                return "Year-round"
    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"XAI API request failed for title '{title}': {e}")
        return "Year-round"


def classify_seasonality(title, categories_sub, manufacturer, xai_api_key=None):
    """
    Classifies a book's seasonality based on title, categories, and manufacturer.
    Uses an LLM as a fallback if heuristics result in "Year-round".

    Args:
        title (str): The title of the book.
        categories_sub (str): The sub-category string.
        manufacturer (str): The manufacturer/publisher of the book.
        xai_api_key (str, optional): The API key for the XAI service.

    Returns:
        str: The classified season, or "Year-round" if no specific season is found.
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

    # --- Fallback to LLM ---
    logger.info(f"Heuristics resulted in 'Year-round' for '{title}'. Falling back to LLM.")
    return _query_xai_for_seasonality(title, categories_sub, manufacturer, xai_api_key)


def get_sells_period(detailed_season):
    """
    Maps a detailed season classification to a specific selling period string.

    Args:
        detailed_season (str): The detailed season name from classify_seasonality.

    Returns:
        str: A string representing the peak selling period (e.g., "Nov-Dec").
             Returns "Non-Seasonal" for "Year-round" classification.
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
        "Year-round": "N/A"
    }
    return period_map.get(detailed_season, "N/A")