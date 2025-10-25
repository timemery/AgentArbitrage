# Restore Dashboard Functionality
import re
import httpx
import json
import logging
import time

# Configure logging
logger = logging.getLogger(__name__)

# --- XAI Rate Limiter ---
# Basic rate limiting to prevent spamming the API.
# This is a simple in-memory implementation suitable for a single-process worker.
XAI_LAST_CALL_TIMESTAMP = 0
XAI_MIN_INTERVAL_SECONDS = 3  # At least 3 seconds between calls

SEASON_CLASSIFICATIONS = [
    "Textbook (Summer)", "Textbook (Winter)", "High School AP Textbooks",
    "Law School", "Nursing School", "Medical School", "Community College",
    "Gardening", "Grilling/BBQ", "Christmas", "New Year/Fitness",
    "Tax Prep", "Travel", "Halloween", "Thanksgiving", "Romance/Valentine's Day",
    "Year-round"
]

def _query_xai_for_seasonality(title, categories_sub, manufacturer, peak_season_str, trough_season_str, api_key):
    """
    Queries the XAI API to classify seasonality, now with sales data insights.
    Includes rate limiting.
    """
    global XAI_LAST_CALL_TIMESTAMP

    # --- Rate Limiting Check ---
    elapsed = time.time() - XAI_LAST_CALL_TIMESTAMP
    if elapsed < XAI_MIN_INTERVAL_SECONDS:
        wait_time = XAI_MIN_INTERVAL_SECONDS - elapsed
        logger.info(f"XAI rate limit: waiting for {wait_time:.2f} seconds.")
        time.sleep(wait_time)

    XAI_LAST_CALL_TIMESTAMP = time.time()

    if not api_key:
        logger.warning("XAI API key is not provided. Skipping LLM classification.")
        return "Year-round"

    prompt = f"""
    Based on the following book details and historical sales data, choose the single most likely sales season from the provided list.
    The sales data indicates when the book's price has historically been highest (peak) and lowest (trough).
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

    # --- DETAILED LOGGING FOR DEBUGGING ---
    logger.info(f"XAI Seasonality Request for ASIN '{title}':")
    logger.info(f"  - Peak: {peak_season_str}, Trough: {trough_season_str}")
    logger.info(f"  - Prompt Snippet: {prompt[:250].replace('\n', ' ')}...") # Log a snippet of the prompt

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

    max_retries = 4
    base_delay = 5 # Start with a 5-second delay

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)

                if response.status_code == 429:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"XAI API rate limit hit for seasonality (attempt {attempt + 1}/{max_retries}). Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()

                # --- DETAILED LOGGING FOR DEBUGGING ---
                logger.info(f"XAI Seasonality Raw Response for ASIN '{title}':\n{json.dumps(data, indent=2)}")

                llm_choice = data['choices'][0]['message']['content'].strip()

                if llm_choice in SEASON_CLASSIFICATIONS:
                    logger.info(f"LLM classified '{title}' as: {llm_choice}")
                    return llm_choice
                else:
                    logger.warning(f"LLM returned an invalid classification: '{llm_choice}'. Defaulting to Year-round.")
                    return "Year-round"

        except (httpx.RequestError, json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"XAI API request failed for title '{title}': {e}")
            return "Year-round" # Fail fast on non-rate-limit errors

    logger.error(f"XAI API (seasonality) failed after {max_retries} retries for title '{title}'. Defaulting to Year-round.")
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