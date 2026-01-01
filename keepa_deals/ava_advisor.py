import os
import json
import logging
import httpx
from datetime import datetime
import traceback

# Setup logger
logger = logging.getLogger('ava_advisor')
logger.setLevel(logging.INFO)

# Load environment variables
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

# Path to strategies file
STRATEGIES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'strategies.json')

def load_strategies():
    """Loads strategies from strategies.json."""
    try:
        if os.path.exists(STRATEGIES_FILE):
            with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
                strategies = json.load(f)
                if isinstance(strategies, list):
                    return "\n".join([f"- {s}" for s in strategies])
    except Exception as e:
        logger.error(f"Error loading strategies: {e}")
    return ""

def query_xai_api(payload, api_key=None):
    """
    Sends a request to the xAI API.
    """
    # Use provided key or fetch lazily
    xai_api_key = api_key if api_key else os.getenv("XAI_TOKEN")

    # Logging API Key Status (Masked)
    if xai_api_key:
        masked_key = xai_api_key[:5] + "..." + xai_api_key[-5:] if len(xai_api_key) > 10 else "***"
        logger.info(f"Using XAI_TOKEN: {masked_key}")
    else:
        logger.error("XAI_TOKEN is not set in environment variables or passed as argument.")
        return {"error": "XAI_TOKEN is not configured."}

    headers = {
        "Authorization": f"Bearer {xai_api_key}",
        "Content-Type": "application/json"
    }

    with httpx.Client(timeout=60.0) as client:
        try:
            logger.info(f"Sending request to xAI API: {XAI_API_URL}")
            response = client.post(XAI_API_URL, headers=headers, json=payload)

            logger.info(f"xAI Response Status Code: {response.status_code}")

            # Log the full response content for debugging (truncate if too long, but keep enough for errors)
            response_text = response.text
            if len(response_text) > 2000:
                 logger.info(f"xAI Response Body (truncated): {response_text[:2000]}...")
            else:
                 logger.info(f"xAI Response Body: {response_text}")

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"xAI API request failed with status {e.response.status_code}: {e.response.text}")
            return {"error": f"API request failed with status {e.response.status_code}", "content": e.response.text}
        except (httpx.RequestError, json.JSONDecodeError) as e:
            logger.error(f"xAI API request failed: {e}")
            logger.error(traceback.format_exc())
            return {"error": str(e)}

def format_currency(value):
    if value is None:
        return "-"
    return f"${value:,.2f}"

def generate_ava_advice(deal_data, xai_api_key=None):
    """
    Generates advice for a specific deal using xAI.

    Args:
        deal_data (dict): Dictionary containing deal details.
        xai_api_key (str, optional): The API key to use.

    Returns:
        str: The generated advice text.
    """
    try:
        title = deal_data.get('Title', 'Unknown Title')
        current_price = deal_data.get('Best_Price')
        avg_price_1yr = deal_data.get('1yr_Avg')
        sales_rank_current = deal_data.get('Sales_Rank_Current')
        sales_rank_365_avg = deal_data.get('Sales_Rank_365_days_avg')
        seasonality = deal_data.get('Detailed_Seasonality', 'Unknown')
        profit = deal_data.get('Profit')
        margin = deal_data.get('Margin')
        percent_down = deal_data.get('Percent_Down')
        trend = deal_data.get('Trend', '')
        drops_365 = deal_data.get('Sales_Rank_Drops_last_365_days', 0)

        # Load learned strategies
        strategies_text = load_strategies()
        strategy_section = ""
        if strategies_text:
            strategy_section = f"""
        **Your Learned Strategies (Use these to inform your advice):**
        {strategies_text}
        """

        # Construct a detailed prompt
        prompt = f"""
        You are Ava, an expert book arbitrage advisor. Your goal is to give a short, concise, and highly actionable paragraph of advice to a user who is considering buying this book to resell.

        **Book Details:**
        *   **Title:** {title}
        *   **Current Buy Price:** {format_currency(current_price)}
        *   **1-Year Average Price:** {format_currency(avg_price_1yr)}
        *   **Percent Down from Avg:** {percent_down}% (Higher is better)
        *   **Current Sales Rank:** {sales_rank_current} (Lower is better)
        *   **1-Year Avg Sales Rank:** {sales_rank_365_avg}
        *   **Sales Rank Drops (Last 365 Days):** {drops_365} (More drops = more sales)
        *   **Seasonality:** {seasonality}
        *   **Estimated Profit:** {format_currency(profit)}
        *   **Margin:** {margin}%
        *   **Price Trend:** {trend}

        **Your Persona & Strategy:**
        *   You are wise, encouraging but cautious. You want the user to succeed.
        *   You replace Keepa. Do not mention Keepa charts explicitly, but use the data to infer what the chart would show (e.g., "consistent demand", "price spikes").
        *   **IMPORTANT:** Be specific about *why* it's good or bad. Mention price history, seasonality, and demand.
        *   If the price is currently low compared to the average, mention it as a buying opportunity.
        *   If the book is seasonal (e.g., Textbook), advise on when to sell (August/September or January).
        *   If the demand (Sales Rank Drops) is low, warn the user.
        *   If the profit is slim, suggest passing unless the volume is high.
        *   Keep it concise (around 50-80 words). No fluff.
        *   Use a conversational tone.
        {strategy_section}

        **Examples of your advice style:**
        *   "Ooo yes good one. At a low price, many recoveries from this low price in the past. Solid demand, no new edition. Nice."
        *   "Hard pass. Price tanking. Even though the demand is still solid I don't expect the price to recover because of the new edition out which has very strong demand."
        *   "Pretty good one, probably have to wait until July/Aug to sell."
        *   "Tough one. Tossup. It is near a low but not many great price spikes in the last few years to buffer against any FBA price drops."
        *   "Not a bad find, but if AMZ drops their price down to $70 ish like earlier in the year, that will cut into profit, so I would probably pass."

        **Write your advice for this specific book:**
        """

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are Ava, a helpful and expert book arbitrage assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-4-fast-reasoning", # Using the latest reasoning model for best results
            "stream": False,
            "temperature": 0.4, # Slightly creative but grounded
            "max_tokens": 150
        }

        result = query_xai_api(payload, api_key=xai_api_key)

        if "error" in result:
            logger.error(f"Error generating advice: {result['error']}")
            return "I'm having trouble analyzing this book right now. Please check the data yourself."

        try:
            advice = result['choices'][0]['message']['content'].strip()
            return advice
        except (KeyError, IndexError):
            logger.error("Unexpected response format from xAI")
            logger.error(f"Full Result: {result}")
            return "I couldn't generate advice for this book."
    except Exception as e:
        logger.error(f"Exception in generate_ava_advice: {e}")
        logger.error(traceback.format_exc())
        return "An unexpected error occurred while generating advice."
