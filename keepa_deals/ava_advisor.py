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

# Path to strategies and intelligence files
STRATEGIES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'strategies.json')
INTELLIGENCE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'intelligence.json')

MENTOR_PERSONAS = {
    'olyvia': {
        'name': 'Olyvia',
        'role': 'CFO Advisor',
        'intro': "Greetings Tim, Olivia here as your CFO advisor. My expertise lies in conservative online arbitrage, business scaling, and Amazon operations—always prioritizing high margins and minimal exposure.",
        'focus': 'Focus on conservative arbitrage, business scaling, high margins, and minimal exposure.',
        'tone': 'Professional, conservative, risk-averse, strategic. Use formal but accessible language.',
        'style_guide': 'Prioritize margin and risk mitigation. Avoid risky bets.',
        'example': '"Pass. The 22% margin is too slim for the current rank volatility. We need 30% minimum to justify the exposure."'
    },
    'joel': {
        'name': 'Joel',
        'role': 'The Flipper',
        'intro': "Yo Tim! My name is Joel, I'll be your mentor today. I'm pumped to help you spot fast-turn deals, crush velocity, and get you in/out quick on Amazon arbitrage. Ask away—let's move product!",
        'focus': 'Focus on velocity, turnover speed, and fast flips.',
        'tone': 'Energetic, informal ("Yo", "pumped"), action-oriented, fast-paced.',
        'style_guide': 'Use exclamation points. Focus on speed of sale. Be direct.',
        'example': '"Buy! Rank is dropping fast. Price is low. Grab 5 copies and flip them before the weekend!"'
    },
    'evelyn': {
        'name': 'Evelyn',
        'role': 'The Professor',
        'intro': "Hello Tim, I'm Evelyn, your professorial mentor in online arbitrage. Allow me to explain concepts like market volatility and profit curves to build your knowledge in business development and Amazon Seller Central.",
        'focus': 'Focus on teaching concepts, market dynamics, and educational growth.',
        'tone': 'Educational, formal, explanatory, patient. Use a teaching tone.',
        'style_guide': 'Explain the "why". Connect data points to concepts (e.g., volatility, curves).',
        'example': '"This is an interesting case. Notice the \'U-shaped\' sales curve? That indicates seasonal textbook demand."'
    },
    'errol': {
        'name': 'Errol',
        'role': 'The Quant',
        'intro': "Hi Tim, I'm Errol, your Quant mentor. I live in the numbers: velocity stats, margin probabilities, historical patterns, Amazon data. I'll give you clean, objective recs backed by hard metrics. Ready when you are.",
        'focus': 'Focus on numbers, velocity stats, margin probabilities, and historical patterns.',
        'tone': 'Objective, data-driven, concise, analytical. Focus on hard metrics.',
        'style_guide': 'Present data in structured format. Focus on variance, confidence intervals, and probabilities.',
        'example': 'Velocity: High (Top 1%)\nPrice Variance: +/- 15%\nRec: Strong Buy based on 3-year historical support levels.'
    }
}

# Map legacy keys to new personas
LEGACY_MENTOR_MAP = {
    'cfo': 'olyvia',
    'flipper': 'joel',
    'professor': 'evelyn',
    'quant': 'errol'
}

# Global cache variables
STRATEGIES_CACHE = None
STRATEGIES_MTIME = 0
INTELLIGENCE_CACHE = None
INTELLIGENCE_MTIME = 0

def get_mentor_config(mentor_name):
    """Retrieves the mentor configuration, handling legacy names."""
    key = mentor_name.lower()
    if key in LEGACY_MENTOR_MAP:
        key = LEGACY_MENTOR_MAP[key]
    return MENTOR_PERSONAS.get(key, MENTOR_PERSONAS['olyvia']) # Default to Olyvia (CFO)

def load_strategies(deal_context=None):
    """
    Loads strategies from strategies.json and formats them for the prompt.
    Uses caching to avoid re-reading file on every request.

    Args:
        deal_context (dict, optional): Context about the deal (e.g., category, seasonality) to filter strategies.
    """
    global STRATEGIES_CACHE, STRATEGIES_MTIME
    try:
        if os.path.exists(STRATEGIES_FILE):
            current_mtime = os.path.getmtime(STRATEGIES_FILE)

            # Reload if cache is empty or file changed
            if STRATEGIES_CACHE is None or current_mtime > STRATEGIES_MTIME:
                # logger.info(f"Loading strategies from disk (mtime: {current_mtime})")
                with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
                    strategies = json.load(f)
                    if isinstance(strategies, list):
                        STRATEGIES_CACHE = strategies
                        STRATEGIES_MTIME = current_mtime
                    else:
                        STRATEGIES_CACHE = [] # Fallback

            strategies = STRATEGIES_CACHE
            if strategies:
                formatted = []

                # Determine relevant categories based on deal_context
                relevant_categories = set(["General", "Buying", "Risk"]) # Always include these

                if deal_context:
                    seasonality = deal_context.get('Detailed_Seasonality', '').lower()
                    title = deal_context.get('Title', '').lower()

                    if 'textbook' in seasonality or 'textbook' in title:
                        relevant_categories.add("Seasonality")

                for s in strategies:
                    if isinstance(s, dict):
                        cat = s.get('category', 'General')
                        if not deal_context or (cat in relevant_categories) or (cat == "General"):
                            formatted.append(f"- [Category: {cat}] IF {s.get('trigger', 'N/A')} THEN {s.get('advice', 'N/A')}")
                    else:
                        formatted.append(f"- {s}")

                return "\n".join(formatted)
    except Exception as e:
        logger.error(f"Error loading strategies: {e}")
    return ""

def load_intelligence():
    """
    Loads intelligence/concepts from intelligence.json and formats them.
    Uses caching to avoid re-reading file on every request.
    """
    global INTELLIGENCE_CACHE, INTELLIGENCE_MTIME
    try:
        if os.path.exists(INTELLIGENCE_FILE):
            current_mtime = os.path.getmtime(INTELLIGENCE_FILE)

            if INTELLIGENCE_CACHE is None or current_mtime > INTELLIGENCE_MTIME:
                # logger.info(f"Loading intelligence from disk (mtime: {current_mtime})")
                with open(INTELLIGENCE_FILE, 'r', encoding='utf-8') as f:
                    intelligence = json.load(f)
                    if isinstance(intelligence, list):
                        INTELLIGENCE_CACHE = intelligence
                        INTELLIGENCE_MTIME = current_mtime
                    else:
                         INTELLIGENCE_CACHE = []

            intelligence = INTELLIGENCE_CACHE
            if intelligence:
                 # Intelligence is usually a list of strings, but now objects
                 formatted_intelligence = []
                 for i in intelligence:
                     if isinstance(i, dict) and 'content' in i:
                         formatted_intelligence.append(f"- {i['content']}")
                     else:
                         formatted_intelligence.append(f"- {i}")
                 return "\n".join(formatted_intelligence)
    except Exception as e:
        logger.error(f"Error loading intelligence: {e}")
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

    # Retry logic configuration
    max_retries = 3
    base_delay = 2  # seconds

    # Increase timeout for reasoning models
    with httpx.Client(timeout=120.0) as client:
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending request to xAI API: {XAI_API_URL} (Attempt {attempt + 1}/{max_retries})")
                response = client.post(XAI_API_URL, headers=headers, json=payload)

                logger.info(f"xAI Response Status Code: {response.status_code}")

                # Log the full response content for debugging
                response_text = response.text
                if len(response_text) > 2000:
                     logger.info(f"xAI Response Body (truncated): {response_text[:2000]}...")
                else:
                     logger.info(f"xAI Response Body: {response_text}")

                # Handle 503 specifically for retry
                if response.status_code == 503:
                    if attempt < max_retries - 1:
                        import time
                        sleep_time = base_delay * (2 ** attempt)
                        logger.warning(f"Got 503 from xAI. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        return {"error": "Service Unavailable (503) after retries."}

                response.raise_for_status()
                return response.json()

            except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                logger.warning(f"Timeout connecting to xAI: {e}. (Attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(base_delay)
                    continue
                return {"error": "The read operation timed out"}

            except httpx.HTTPStatusError as e:
                # 4xx errors should not be retried usually, unless it's 429
                if e.response.status_code == 429:
                     if attempt < max_retries - 1:
                        import time
                        time.sleep(5) # Fixed wait for rate limit
                        continue

                logger.error(f"xAI API request failed with status {e.response.status_code}: {e.response.text}")
                return {"error": f"API request failed with status {e.response.status_code}", "content": e.response.text}

            except (httpx.RequestError, json.JSONDecodeError) as e:
                # Network errors that are not timeouts might be worth one retry
                if attempt < max_retries - 1:
                     import time
                     time.sleep(base_delay)
                     continue

                logger.error(f"xAI API request failed: {e}")
                logger.error(traceback.format_exc())
                return {"error": str(e)}

        return {"error": "Max retries exceeded."}

def format_currency(value):
    if value is None:
        return "-"
    try:
        if isinstance(value, str):
            value = float(value.replace('$', '').replace(',', ''))
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return str(value)

def generate_ava_advice(deal_data, mentor_type='cfo', xai_api_key=None):
    """
    Generates advice for a specific deal using xAI.
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
        mentor = get_mentor_config(mentor_type)

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
        You are {mentor['name']}, {mentor['role']}. Your goal is to give advice to a user who is considering buying this book to resell.

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
        *   **Context Aware:** Apply your learned strategies (below) to identify risks.
        *   **Constraint:** Do NOT start with an introduction. Jump straight into the analysis.
        *   **Constraint:** Do NOT use markdown formatting (no bolding, no headers, no bullet points). Use plain text paragraphs only.

        {strategy_section}

        **Example of your advice style:**
        {mentor['example']}

        **Write your advice for this specific book:**
        """

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": f"You are {mentor['name']}, an expert book arbitrage assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-4-fast-reasoning",
            "stream": False,
            "temperature": 0.4,
            "max_tokens": 150
        }

        result = query_xai_api(payload, api_key=xai_api_key)

        if "error" in result:
            logger.error(f"Error generating advice: {result['error']}")
            return "Mentor unexpectedly failed ... Please try again"

        try:
            advice = result['choices'][0]['message']['content'].strip()
            return advice
        except (KeyError, IndexError):
            logger.error("Unexpected response format from xAI")
            return "Mentor unexpectedly failed ... Please try again"
    except Exception as e:
        logger.error(f"Exception in generate_ava_advice: {e}")
        logger.error(traceback.format_exc())
        return "Mentor unexpectedly failed ... Please try again"
