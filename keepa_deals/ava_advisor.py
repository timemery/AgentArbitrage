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

from .platform_knowledge import get_platform_knowledge

STRATEGIC_CORRECTIONS = """
        IMPORTANT — TEXTBOOK COUNTERFEIT RISK CORRECTION: Some strategies you have been given may suggest categorical rejection of textbooks (medical, engineering, AP, college subjects, etc.) due to counterfeit risk. This is overcautious and incorrect. Do NOT reject textbook candidates based on category alone or subject area alone.

        Counterfeit risk is genuinely HIGH only when ALL FOUR of the following conditions are met simultaneously:

        1. Sales Rank is under 100,000 (high current demand)
        2. Price is significantly below historical market average
        3. Condition is New or Like-New
        4. Seller has limited feedback or appears to be moving multiple new-condition copies at suspiciously low prices

        One, two, or three of these factors alone is NOT a counterfeit signal. Only all four together is the red flag pattern.

        Books with Sales Rank above 500,000 are very unlikely to be counterfeit regardless of category. Older editions of textbooks are also unlikely to be counterfeit. Apply the four-factor test specifically — do not reject on category.

        This correction takes priority over any general strategies suggesting textbook avoidance.

        IMPORTANT — SEASONAL HIGH-RANK CORRECTION: Some candidates will have a high current sales rank (over 1,000,000) but be flagged in `Detailed_Seasonality` as a seasonal title (e.g., "Medical School", "Christmas", "Summer Reading", "Spring Gardening", or any season-specific category). Do NOT reject seasonal candidates solely based on current high sales rank.

        A book that ranks 1.5M in the off-season may rank 200K-400K during its season, with strong ROI for buyers willing to hold inventory. The ROI on seasonal flips often exceeds high-velocity flips because the off-season buy price is depressed. The seller plans inventory by holding books at their own prep warehouse and shipping to Amazon 2-3 months before the selling season to minimize FBA aged-inventory surcharges (which begin at 181 days and escalate steeply at 271+ days).

        Apply the high-rank rejection rule strictly only when the candidate is classified as "Year-round" or has no clear seasonal classification. For seasonal candidates, prioritize offer-trend stability and discount depth over current rank.

        This correction takes priority over general velocity-based rejection rules.

        The seller actively pursues TWO equally-valid arbitrage strategies:

        1. **High-velocity flips** — books with sales rank under 1M and frequent drops, for fast capital turnover and steady cash flow.

        2. **Seasonal holds** — books with high off-season rank that rank substantially better during their selling season (e.g., textbooks ranking 5M in summer but 300K in fall), for higher ROI per unit at the cost of inventory holding time.

        Neither strategy is preferred over the other. A book that fits Strategy 2 is NOT "speculative" or "tying up capital" — it is a deliberate choice with quantified trade-offs (FBA aged-inventory surcharges begin at 181 days and escalate sharply at 271+ days; the seller manages this by holding inventory at their own prep warehouse and shipping to Amazon 2-3 months before the selling season).

        Mentor recommendations must evaluate each candidate against the strategy it best fits:
        - For candidates classified as "Year-round" or with no clear seasonal classification: apply Strategy 1 reasoning. High rank or low velocity is a legitimate reason to pass.
        - For candidates with a clear seasonal classification (textbooks, Christmas, summer reading, gardening, fitness/New Year, etc.): apply Strategy 2 reasoning. Evaluate offer-trend stability, discount depth, and the gap between current rank and likely in-season rank — not the off-season rank alone.

        Do NOT recommend "redirect funds to replens with proven year-round demand" as a default closer for seasonal candidates. That phrasing implies Strategy 2 is inferior to Strategy 1, which is not the seller's view.

"""

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
    max_retries = 5
    base_delay = 3  # seconds

    import requests

    # Increase timeout for reasoning models
    for attempt in range(max_retries):
        try:
            logger.info(f"Sending request to xAI API: {XAI_API_URL} (Attempt {attempt + 1}/{max_retries})")

            # Using requests instead of httpx because httpx sometimes hangs indefinitely in WSGI context
            response = requests.post(XAI_API_URL, headers=headers, json=payload, timeout=150.0)

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

        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout connecting to xAI: {e}. (Attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                import time
                time.sleep(base_delay)
                continue
            return {"error": "The read operation timed out"}

        except requests.exceptions.HTTPError as e:
            # 4xx errors should not be retried usually, unless it's 429
            if response.status_code == 429:
                 if attempt < max_retries - 1:
                    import time
                    time.sleep(5) # Fixed wait for rate limit
                    continue

            logger.error(f"xAI API request failed with status {response.status_code}: {response.text}")
            return {"error": f"API request failed with status {response.status_code}", "content": response.text}

        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
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

TOOLTIP_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tooltip_cache.json')

def load_tooltip_cache():
    if os.path.exists(TOOLTIP_CACHE_FILE):
        try:
            with open(TOOLTIP_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_tooltip_cache(cache):
    try:
        with open(TOOLTIP_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save tooltip cache: {e}")

def generate_tooltip_advice(term, xai_api_key=None):
    """
    Generates a succinct tooltip for a UI term using platform knowledge.
    """
    cache = load_tooltip_cache()
    if term in cache:
        return cache[term]

    try:
        platform_knowledge = get_platform_knowledge()

        prompt = f"""
        You are an expert assistant for the Agent Arbitrage platform.
        Your task is to provide a very brief, contextual tooltip explanation for the following UI term/feature: "{term}".

        **Platform Knowledge Base:**
        {platform_knowledge}

        **Rules for Tooltips (CRITICAL):**
        *   **Be Succinct:** 2-5 words is ideal.
        *   **Character Limit:** 20-30 characters preferred. Absolute maximum is 150 characters.
        *   **No "Walls of Text":** Maximum 3 lines.
        *   **Focus:** Explain a single action or define a term.
        *   **Format:** Sentence case.
        *   **Style:** Use "Verb + Noun" when applicable.
        *   **Non-Redundant:** Do not just repeat the visible label.
        *   **Specific Instructions**: For arrows in columns like "Age", explicitly mention their meaning based on documentation (e.g. Up = Price increased, Down = Price decreased).
        *   Do NOT explain underlying code mechanics. Only explain how to use the tool or what the data means based on the documentation.

        **Provide the tooltip text ONLY:**
        """

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a UX copywriter for Agent Arbitrage."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-4-fast-reasoning",
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 100
        }

        result = query_xai_api(payload, api_key=xai_api_key)

        if "error" in result:
            logger.error(f"Error generating tooltip for {term}: {result['error']}")
            return "Help currently unavailable."

        try:
            advice = result['choices'][0]['message']['content'].strip()
            # Strip quotes if the LLM added them
            if advice.startswith('"') and advice.endswith('"'):
                advice = advice[1:-1]

            cache[term] = advice
            save_tooltip_cache(cache)
            return advice
        except (KeyError, IndexError):
            logger.error(f"Unexpected response format from xAI for tooltip: {term}")
            return "Help currently unavailable."
    except Exception as e:
        logger.error(f"Exception in generate_tooltip_advice: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return "Help currently unavailable."

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

        # Load Platform Knowledge
        platform_knowledge = get_platform_knowledge()
        platform_section = ""
        if platform_knowledge:
            platform_section = f"""
        **Platform Knowledge Base (Use to answer questions about the platform itself, do not explain underlying code mechanics):**
        {platform_knowledge}
        """

        # Construct a detailed prompt
        prompt = f"""
        You are {mentor['name']}, {mentor['role']}. Your goal is to give advice to a user who is considering buying this book to resell.

        {platform_section}

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
        *   **Constraint:** Do NOT start with an introduction or preamble. Jump straight into the analysis.
        *   **Constraint:** Do NOT use markdown formatting (like **bold**). Use ONLY HTML tags (e.g., <b>, <br>, <p>) for formatting.
        *   **Goal:** Provide a dense, high-quality analysis in approximately 150-180 words. Be concise but do not sacrifice depth.

        {strategy_section}

        **Example of your advice style:**
        {mentor['example']}

        {STRATEGIC_CORRECTIONS}

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
            "max_tokens": 1000
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
