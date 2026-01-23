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

MENTOR_PERSONAS = {
    'cfo': {
        'role': 'an analytical, professional, and cautious business advisor',
        'focus': 'Focus on Business Objectives: Profit, Demand (Velocity), and Risk Management. Be Risk-Averse.',
        'tone': 'Professional, objective, and concise (50-80 words).',
        'style_guide': 'Avoid "wishy-washy" language. Give a clear "Buy" or "Pass" recommendation based on the data. Highlight margins and "don\'t lose money" scenarios.',
        'example': '"Pass. The 22% margin is too slim for the current rank volatility."'
    },
    'flipper': {
        'role': 'an aggressive, high-volume flipper',
        'focus': 'Focus on Velocity, turnover speed, and "get in, get out".',
        'tone': 'Short, punchy, energetic (30-50 words).',
        'style_guide': 'Use exclamation points for good deals. Be direct. Focus on speed of sale.',
        'example': '"Buy! Rank is dropping fast. Price is low. Grab 5 copies and flip them before the weekend."'
    },
    'professor': {
        'role': 'an educational mentor and book arbitrage expert',
        'focus': 'Focus on teaching *why* a deal is good or bad, citing specific concepts.',
        'tone': 'Verbose, patient, explanatory (80-100 words).',
        'style_guide': 'Explain the "why". Connect data points (e.g., "U-shaped sales curve indicates seasonal demand"). Use a teaching tone.',
        'example': '"This is an interesting case. Notice the \'U-shaped\' sales curve? That indicates seasonal textbook demand. Although the current price is low..."'
    },
    'quant': {
        'role': 'a quantitative analyst and data scientist',
        'focus': 'Focus on statistical confidence, historical averages, and objective metrics.',
        'tone': 'Dry, robotic, purely objective. Use bullet points.',
        'style_guide': 'Present data in structured format. Focus on variance, confidence intervals, and probabilities.',
        'example': 'Velocity: High (Top 1%)\nPrice Variance: +/- 15%\nRec: Strong Buy based on 3-year historical support levels.'
    }
}

def load_strategies(deal_context=None):
    """
    Loads strategies from strategies.json and formats them for the prompt.

    Args:
        deal_context (dict, optional): Context about the deal (e.g., category, seasonality) to filter strategies.
    """
    try:
        if os.path.exists(STRATEGIES_FILE):
            with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
                strategies = json.load(f)
                if isinstance(strategies, list):
                    formatted = []

                    # Determine relevant categories based on deal_context
                    relevant_categories = set(["General", "Buying", "Risk"]) # Always include these

                    if deal_context:
                        seasonality = deal_context.get('Detailed_Seasonality', '').lower()
                        title = deal_context.get('Title', '').lower()

                        if 'textbook' in seasonality or 'textbook' in title:
                            relevant_categories.add("Seasonality")

                        # Add more logic here as needed, e.g. based on Sales Rank or ROI triggers

                    for s in strategies:
                        if isinstance(s, dict):
                            cat = s.get('category', 'General')
                            # If we have context, try to filter. If cat is in our relevant set, include it.
                            # If cat is None or empty, treat as General.
                            if not deal_context or (cat in relevant_categories) or (cat == "General"):
                                formatted.append(f"- [Category: {cat}] IF {s.get('trigger', 'N/A')} THEN {s.get('advice', 'N/A')}")
                        else:
                            # Legacy strings are always included as we can't categorize them easily without processing
                            formatted.append(f"- {s}")

                    return "\n".join(formatted)
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
    try:
        # Try to convert string to float if necessary
        if isinstance(value, str):
            value = float(value.replace('$', '').replace(',', ''))
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        # If conversion fails, return the original string
        return str(value)

def generate_ava_advice(deal_data, mentor_type='cfo', xai_api_key=None):
    """
    Generates advice for a specific deal using xAI.

    Args:
        deal_data (dict): Dictionary containing deal details.
        mentor_type (str): The persona to adopt ('cfo', 'flipper', 'professor', 'quant').
        xai_api_key (str, optional): The API key to use.

    Returns:
        str: The generated advice text.
    """
    try:
        title = deal_data.get('Title', 'Unknown Title')
        current_price = deal_data.get('Price_Now') or deal_data.get('Best_Price')
        avg_price_1yr = deal_data.get('1yr_Avg')
        sales_rank_current = deal_data.get('Sales_Rank_Current')
        sales_rank_365_avg = deal_data.get('Sales_Rank_365_days_avg')
        seasonality = deal_data.get('Detailed_Seasonality', 'Unknown')
        profit = deal_data.get('Profit')
        margin = deal_data.get('Margin')
        percent_down = deal_data.get('Percent_Down')
        trend = deal_data.get('Trend', '')
        drops_365 = deal_data.get('Sales_Rank_Drops_last_365_days', 0)

        # Get Mentor Persona
        mentor = MENTOR_PERSONAS.get(mentor_type.lower(), MENTOR_PERSONAS['cfo'])

        # Load learned strategies with context
        strategies_text = load_strategies(deal_context=deal_data)
        strategy_section = ""
        if strategies_text:
            strategy_section = f"""
        **Your Learned Strategies (Use these to inform your advice):**
        {strategies_text}
        """

        # Construct a detailed prompt
        prompt = f"""
        You are Ava, {mentor['role']}. Your goal is to give advice to a user who is considering buying this book to resell.

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
        *   **Focus:** {mentor['focus']}
        *   **Tone:** {mentor['tone']}
        *   **Style:** {mentor['style_guide']}
        *   **Context Aware:** Apply your learned strategies (below) to identify risks (e.g., prohibited items, restriction risks).

        {strategy_section}

        **Example of your advice style:**
        {mentor['example']}

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
