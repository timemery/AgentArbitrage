import logging
import sqlite3
import json
import re
import uuid
from datetime import datetime, timezone
import os

from worker import celery_app as celery
from .db_utils import DB_PATH
from .ava_advisor import query_xai_api, STRATEGIES_FILE
from .new_analytics import get_offer_count_trend_from_flat
from keepa_deals.db_utils import get_db_connection

logger = logging.getLogger(__name__)

PASS_1_MIN_PROFIT = 15
PASS_1_MIN_ROI = 20
PASS_1_MAX_ROI = 300
PASS_1_MIN_DEAL_TRUST = 50
PASS_1_MAX_LIST_AT = 500
PASS_1_OFFER_TREND_VELOCITY_GATE = 100000
PASS_1_OFFER_TREND_BONUS_MULTIPLIER = 1.1
PASS_1_YEAR_ROUND_VELOCITY_CAP = 2000000

def get_tiered_strategies(candidates, max_per_core_category=30):
    """
    Implements tiered strategy injection (Pass 2 payload reduction).
    - Takes only 'High' confidence strategies from core categories, capped at max_per_core_category.
    - Dynamically adds specific category strategies if they match candidate keywords.
    """
    try:
        with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
            strategies = json.load(f)
    except Exception as e:
        logger.error(f"Error reading strategies: {e}")
        return ""

    core_categories = {"General", "Risk", "Buying", "Pricing"}

    # Extract keywords from candidates to find relevant dynamic categories
    candidate_text = ""
    for c in candidates:
        candidate_text += f"{c.get('Title', '')} {c.get('Detailed_Seasonality', '')} ".lower()

    dynamic_categories = set()
    if 'textbook' in candidate_text:
        dynamic_categories.add('Seasonality')

    # Group strategies
    categorized = {cat: [] for cat in core_categories}
    for cat in dynamic_categories:
        categorized[cat] = []

    for s in strategies:
        if not isinstance(s, dict):
            continue

        cat = s.get('category', 'General')
        conf = s.get('confidence', '')

        # Core categories: only High confidence
        if cat in core_categories and conf == 'High':
            categorized[cat].append(s)
        # Dynamic categories: include all relevant (or also limit to High if desired)
        elif cat in dynamic_categories and conf == 'High':
            categorized[cat].append(s)

    formatted = []

    # Append core strategies up to the cap
    for cat in core_categories:
        # Sort or just take first N? The existing list order is somewhat arbitrary,
        # but since they are all 'High' confidence, the first N is a good stable subset.
        for s in categorized[cat][:max_per_core_category]:
            formatted.append(f"- [Category: {cat}] IF {s.get('trigger', 'N/A')} THEN {s.get('advice', 'N/A')}")

    # Append dynamic strategies
    for cat in dynamic_categories:
        for s in categorized[cat][:max_per_core_category]:
            formatted.append(f"- [Category: {cat}] IF {s.get('trigger', 'N/A')} THEN {s.get('advice', 'N/A')}")

    return "\n".join(formatted)

def get_hours_since(date_str):
    if not date_str:
        return 0
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.utcnow()
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        delta = now - dt
        return max(0, delta.total_seconds() / 3600.0)
    except ValueError:
        try:
            dt = datetime.strptime(date_str, '%m/%d/%y %H:%M')
            now = datetime.utcnow()
            delta = now - dt
            return max(0, delta.total_seconds() / 3600.0)
        except ValueError:
            return 0

def parse_offers(offers_str):
    if not offers_str or offers_str == '-': return 0
    m = re.search(r'(\d+)', str(offers_str))
    if m:
        return int(m.group(1))
    return 0

@celery.task(name='keepa_deals.prime_picks_task.generate_prime_picks')
def generate_prime_picks():
    """
    Executes the async Two-Pass Prime Picks pipeline.
    Pass 1: Smart Floor SQL/math filtering & scoring
    Pass 2: xAI Mastermind batched evaluation
    """
    logger.info("Starting Async Prime Picks Pipeline")

    try:
        # Pass 1: Smart Floor
        with get_db_connection(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sanitized_profit = "CAST(REPLACE(REPLACE(\"Profit\", '$', ''), ',', '') AS REAL)"
            sanitized_cost = "CAST(REPLACE(REPLACE(\"All_in_Cost\", '$', ''), ',', '') AS REAL)"
            sanitized_list_at = "CAST(REPLACE(REPLACE(\"List_at\", '$', ''), ',', '') AS REAL)"

            # Additional ROI cap at 300% added per requirements
            roi_expr = f"(({sanitized_profit} * 1.0 / {sanitized_cost}) * 100)"

            query = f"""
                SELECT * FROM deals
                WHERE {sanitized_profit} >= {PASS_1_MIN_PROFIT}
                AND {sanitized_cost} > 0
                AND {roi_expr} >= {PASS_1_MIN_ROI}
                AND {roi_expr} <= {PASS_1_MAX_ROI}
                AND CAST(REPLACE(\"Deal_Trust\", '%', '') AS REAL) >= {PASS_1_MIN_DEAL_TRUST}
                AND \"List_at\" IS NOT NULL
                AND {sanitized_list_at} > 0
                AND {sanitized_list_at} <= {PASS_1_MAX_LIST_AT}
                AND \"1yr_Avg\" IS NOT NULL
                AND \"1yr_Avg\" NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00')
                AND \"1yr_Avg\" != 0
            """

            deal_rows = cursor.execute(query).fetchall()
            deals_list = [dict(row) for row in deal_rows]

        logger.info(f"Pass 1: Found {len(deals_list)} candidates matching Smart Floor.")

        if not deals_list:
            logger.info("No candidates found. Exiting.")
            return

        # Score the candidates
        filtered_deals = []
        dropped_candidates = 0
        no_trend_candidates = 0
        dropped_year_round_high_rank = 0

        for deal in deals_list:
            profit_str = str(deal.get('Profit', '0')).replace('$', '').replace(',', '')
            cost_str = str(deal.get('All_in_Cost', '0')).replace('$', '').replace(',', '')
            try:
                profit = float(profit_str)
                cost = float(cost_str)
                roi = (profit / cost) * 100 if cost > 0 else 0
            except ValueError:
                profit = 0
                roi = 0

            hours_since = get_hours_since(deal.get('last_seen_utc') or deal.get('Deal_found'))

            sales_rank = deal.get('Sales_Rank_Current')
            if sales_rank is None or sales_rank == '':
                sales_rank = 1000000
            else:
                try:
                    sales_rank = float(str(sales_rank).replace(',', ''))
                except ValueError:
                    sales_rank = 1000000

            offers = parse_offers(deal.get('Offers'))

            base_half_life = 24 + (sales_rank / 2000000.0) * 144
            final_half_life = base_half_life * (1 - min(0.5, offers * 0.02))

            score = (profit * roi) * (0.5 ** (hours_since / max(0.001, final_half_life)))

            # Year-Round Velocity Cap Filter
            drop_candidate = False
            seasonality = str(deal.get('Detailed_Seasonality', '')).lower().strip()
            if seasonality == 'year-round' and sales_rank > PASS_1_YEAR_ROUND_VELOCITY_CAP:
                logger.info(f"[Pass 1 Filter] Dropped ASIN={deal.get('ASIN')} (seasonality={seasonality}, sales_rank={sales_rank}) — year-round + high rank")
                dropped_year_round_high_rank += 1
                drop_candidate = True

            # Offer Trend Modifier
            trend = get_offer_count_trend_from_flat(deal)

            if not drop_candidate and trend == 'rising' and sales_rank > PASS_1_OFFER_TREND_VELOCITY_GATE:
                logger.info(f"[Pass 1 Filter] Dropped ASIN={deal.get('ASIN')} (trend=rising, sales_rank={sales_rank}) — rising offers + weak velocity")
                dropped_candidates += 1
                drop_candidate = True
            elif trend in ('falling', 'flat'):
                offer_trend_modifier = PASS_1_OFFER_TREND_BONUS_MULTIPLIER
            elif trend is None:
                offer_trend_modifier = 1.0
                no_trend_candidates += 1
                logger.info(f"[Pass 1 Filter] No trend signal for ASIN={deal.get('ASIN')} — passing through with no modifier")
            else:
                offer_trend_modifier = 1.0

            if not drop_candidate:
                score = score * offer_trend_modifier
                deal['_score'] = score
                filtered_deals.append(deal)

        logger.info(f"[Pass 1 Filter] Offer-trend filter dropped {dropped_candidates} of {len(deals_list)} candidates; {no_trend_candidates} had no trend signal; Year-round high rank dropped {dropped_year_round_high_rank}")

        # Top 20 candidates
        filtered_deals.sort(key=lambda x: x.get('_score', 0), reverse=True)
        top_20 = filtered_deals[:20]

        logger.info(f"Pass 1: Top {len(top_20)} candidates selected for xAI evaluation.")

        # Pass 2: xAI Evaluation
        strategies_text = get_tiered_strategies(top_20)

        candidates_for_ai = []
        for d in top_20:
            candidates_for_ai.append({
                "ASIN": d.get("ASIN"),
                "Title": d.get("Title", "")[:100],
                "Sales_Rank_Current": d.get("Sales_Rank_Current"),
                "Offers": d.get("Offers"),
                "Sales_Rank_Drops_last_180_days": d.get("Sales_Rank_Drops_last_180_days"),
                "Profit": d.get("Profit"),
                "Detailed_Seasonality": d.get("Detailed_Seasonality"),
                "Percent_Down": d.get("Percent_Down")
            })

        prompt = f"""
        You are the xAI Mastermind evaluating the top candidate deals.

        **Evaluation Strategy:**
        You MUST evaluate candidates holistically against ALL strategies present in the provided text rules. However, recognize that not every deal will be a "perfect" match for every strategy (e.g. not everything needs to be seasonal).

        Strategies:
        {strategies_text}

        **Candidates:**
        {json.dumps(candidates_for_ai, indent=2)}

        **Instructions:**
        Evaluate the items (ASINs) and determine if they represent solid arbitrage opportunities based on the strategies. Filter out any deals that violate key risk management rules or are obviously poor choices, but allow good standard deals to pass.
        You MUST return a JSON object containing two keys: "selected" and "rejected". The "selected" key should contain a list of objects with the ASIN and a brief 1-sentence reason. The "rejected" key should contain a list of objects with the ASIN and a brief 1-sentence reason.
        Example:
        {{
          "selected": [{{"asin": "0123456789", "reason": "High ROI and stable BSR trend."}}],
          "rejected": [{{"asin": "B01ABCD123", "reason": "Sales rank is too erratic indicating high risk."}}]
        }}
        You MUST return ONLY the JSON object. No markdown formatting, no other explanations.
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

        """

        payload = {
            "messages": [
                {"role": "system", "content": "You are a precise JSON-only output bot."},
                {"role": "user", "content": prompt}
            ],
            "model": "grok-4-fast-reasoning",
            "stream": False,
            "temperature": 0.2
        }

        import time
        prompt_size = len(prompt)
        logger.info(f"Pass 2: Querying xAI API (prompt size: {prompt_size} chars)...")
        start_time = time.time()
        response_data = query_xai_api(payload)
        latency = time.time() - start_time
        logger.info(f"Pass 2: xAI API call took {latency:.2f} seconds.")

        selected_asins = []
        ai_failed = False

        if not response_data or "error" in response_data:
            logger.error(f"xAI API returned an error: {response_data.get('error', 'Unknown Error')}")
            ai_failed = True
        elif 'choices' in response_data and response_data['choices']:
            message = response_data['choices'][0].get('message', {})
            content = message.get('content', '').strip()

            # Log the full raw text (which might contain reasoning if the model provides it)
            logger.info(f"Pass 2 Raw Response: {content}")

            # Extract JSON block if it is wrapped in markdown
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, flags=re.DOTALL)
            if json_match:
                content_clean = json_match.group(1).strip()
            else:
                content_clean = content.strip()
                # Find the first { and last } if it's not wrapped in backticks
                start_idx = content_clean.find('{')
                end_idx = content_clean.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    content_clean = content_clean[start_idx:end_idx+1]

            try:
                parsed = json.loads(content_clean)
                reasoning_map = {}
                selected_asins = []

                if isinstance(parsed, dict):
                    selected_list = parsed.get("selected", [])
                    rejected_list = parsed.get("rejected", [])

                    if isinstance(selected_list, list) and len(selected_list) > 0 and isinstance(selected_list[0], str):
                         # Fallback if xAI returned strings instead of dicts for selected
                         selected_asins = [str(x) for x in selected_list]
                         for asin in selected_asins:
                             reasoning_map[asin] = "No reason provided (legacy array format)"
                    else:
                        for item in selected_list:
                            if isinstance(item, dict) and "asin" in item:
                                asin = str(item["asin"])
                                selected_asins.append(asin)
                                reasoning_map[asin] = str(item.get("reason", ""))

                    for item in rejected_list:
                        if isinstance(item, dict) and "asin" in item:
                            reasoning_map[str(item["asin"])] = str(item.get("reason", ""))

                # Log reasoning per ASIN
                for c in candidates_for_ai:
                    asin = str(c.get("ASIN"))
                    is_selected = asin in selected_asins
                    reason = reasoning_map.get(asin, "See raw response")

                    logger.info(f"[Pass 2 Reasoning] ASIN={asin} Selected={is_selected} Reason=\"{reason}\"")

            except json.JSONDecodeError:
                logger.error(f"Failed to parse xAI output as JSON: {content}")
                ai_failed = True
        else:
            ai_failed = True

        # Fallback to Pass 1 if Pass 2 fails
        if ai_failed:
            logger.info(f"Pass 2 failed. Preserving previous valid run instead of overriding cache.")
            return
        else:
            final_deals = [d for d in top_20 if str(d.get("ASIN")) in selected_asins]
            if not final_deals:
                logger.info("Pass 2 returned empty list. Preserving previous valid run.")
                return

        logger.info(f"Pass 2 complete. Selected {len(final_deals)} Prime Picks.")

        # Insert into prime_picks table
        run_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()

        records_to_insert = []
        for rank_idx, d in enumerate(final_deals, start=1):
            records_to_insert.append((
                str(d.get("ASIN")),
                rank_idx,
                float(d.get("_score", 0)),
                generated_at,
                run_id
            ))

        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()

            # Atomic replace:
            cursor.execute("BEGIN TRANSACTION")
            try:
                # Delete old run
                cursor.execute("DELETE FROM prime_picks")
                # Insert new run
                cursor.executemany("""
                    INSERT INTO prime_picks (asin, rank, score, generated_at, run_id)
                    VALUES (?, ?, ?, ?, ?)
                """, records_to_insert)
                cursor.execute("COMMIT")
                logger.info(f"Successfully saved {len(records_to_insert)} Prime Picks to database (run_id: {run_id}).")
            except Exception as e:
                cursor.execute("ROLLBACK")
                logger.error(f"Failed to save Prime Picks to DB: {e}")
                raise

    except Exception as e:
        logger.error(f"Error in generate_prime_picks task: {e}", exc_info=True)
