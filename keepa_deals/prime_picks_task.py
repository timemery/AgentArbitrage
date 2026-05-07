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

logger = logging.getLogger(__name__)

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
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sanitized_profit = "CAST(REPLACE(REPLACE(\"Profit\", '$', ''), ',', '') AS REAL)"
            sanitized_cost = "CAST(REPLACE(REPLACE(\"All_in_Cost\", '$', ''), ',', '') AS REAL)"
            sanitized_list_at = "CAST(REPLACE(REPLACE(\"List_at\", '$', ''), ',', '') AS REAL)"

            # Additional ROI cap at 300% added per requirements
            roi_expr = f"(({sanitized_profit} * 1.0 / {sanitized_cost}) * 100)"

            query = f"""
                SELECT * FROM deals
                WHERE {sanitized_profit} >= 10
                AND {sanitized_cost} > 0
                AND {roi_expr} >= 15
                AND {roi_expr} <= 300
                AND CAST(REPLACE(\"Deal_Trust\", '%', '') AS REAL) >= 40
                AND \"List_at\" IS NOT NULL
                AND {sanitized_list_at} > 0
                AND {sanitized_list_at} <= 1500
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
            deal['_score'] = score

        # Top 20 candidates
        deals_list.sort(key=lambda x: x.get('_score', 0), reverse=True)
        top_20 = deals_list[:20]

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
        Select the items (ASINs) that represent solid arbitrage opportunities based on the strategies. Filter out any deals that violate key risk management rules or are obviously poor choices, but allow good standard deals to pass.
        You MUST return ONLY a JSON array of strings containing the selected ASINs. No markdown formatting, no explanations.
        Example: ["0123456789", "B01ABCD123"]
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

        logger.info("Pass 2: Querying xAI API...")
        response_data = query_xai_api(payload)

        selected_asins = []
        ai_failed = False

        if not response_data or "error" in response_data:
            logger.error(f"xAI API returned an error: {response_data.get('error', 'Unknown Error')}")
            ai_failed = True
        elif 'choices' in response_data and response_data['choices']:
            content = response_data['choices'][0].get('message', {}).get('content', '').strip()
            content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip(), flags=re.MULTILINE).strip()
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    selected_asins = [str(x) for x in parsed]
                elif isinstance(parsed, dict) and "asins" in parsed:
                    selected_asins = [str(x) for x in parsed["asins"]]
            except json.JSONDecodeError:
                logger.error(f"Failed to parse xAI output as JSON: {content}")
                ai_failed = True
        else:
            ai_failed = True

        # Fallback to Pass 1 if Pass 2 fails
        if ai_failed:
            logger.info(f"Pass 2 failed. Falling back to all {len(top_20)} top candidates.")
            final_deals = top_20
        else:
            final_deals = [d for d in top_20 if str(d.get("ASIN")) in selected_asins]
            if not final_deals:
                logger.info("Pass 2 returned empty list. Falling back to top 20.")
                final_deals = top_20

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

        with sqlite3.connect(DB_PATH) as conn:
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
