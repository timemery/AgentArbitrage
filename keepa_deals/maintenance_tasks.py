from logging import getLogger
import os
import json
import redis
import re
from datetime import datetime
from worker import celery_app as celery
from .ava_advisor import query_xai_api

logger = getLogger(__name__)

# Use CWD to ensure we target the deployment directory, avoiding issues with module location
INTELLIGENCE_FILE = os.path.join(os.getcwd(), 'intelligence.json')
HOMOGENIZATION_STATUS_KEY = "homogenization_status"

@celery.task(name='keepa_deals.maintenance_tasks.homogenize_intelligence_task')
def homogenize_intelligence_task():
    """Background task to homogenize intelligence.json using LLM."""
    redis_client = redis.Redis.from_url(celery.conf.broker_url)

    # Initialize status
    redis_client.set(HOMOGENIZATION_STATUS_KEY, json.dumps({
        "status": "Running",
        "progress": "Starting...",
        "removed_count": 0
    }))

    logger.info(f"Homogenization Task Started. CWD: {os.getcwd()}")
    logger.info(f"Target Intelligence File: {INTELLIGENCE_FILE}")

    if not os.path.exists(INTELLIGENCE_FILE):
        error_msg = f"File not found: {INTELLIGENCE_FILE}"
        logger.error(error_msg)
        redis_client.set(HOMOGENIZATION_STATUS_KEY, json.dumps({"status": "Error", "message": error_msg}))
        return 0

    try:
        # Reload from disk to ensure freshness (avoid stale memory state)
        with open(INTELLIGENCE_FILE, 'r', encoding='utf-8') as f:
            intelligence = json.load(f)

        if not intelligence:
            redis_client.set(HOMOGENIZATION_STATUS_KEY, json.dumps({"status": "Complete", "removed_count": 0}))
            return 0

        # Create mapping of content -> date_added to preserve dates
        content_date_map = {}
        for item in intelligence:
            if isinstance(item, dict) and 'content' in item:
                content_date_map[str(item['content']).strip()] = item.get('date_added')
            elif isinstance(item, str):
                # Fallback for strings (should be rare after migration)
                content_date_map[str(item).strip()] = None

        # Extract just the content strings for LLM processing
        intelligence_content_list = []
        for item in intelligence:
            if isinstance(item, dict) and 'content' in item:
                intelligence_content_list.append(str(item['content']).strip())
            else:
                intelligence_content_list.append(str(item).strip())

        CHUNK_SIZE = 500
        total_original = len(intelligence_content_list)
        all_cleaned_strings = []

        logger.info(f"Starting processing for {total_original} items...")

        for i in range(0, total_original, CHUNK_SIZE):
            chunk = intelligence_content_list[i:i + CHUNK_SIZE]
            current_chunk_num = (i // CHUNK_SIZE) + 1
            total_chunks = (total_original + CHUNK_SIZE - 1) // CHUNK_SIZE

            # Update status
            redis_client.set(HOMOGENIZATION_STATUS_KEY, json.dumps({
                "status": "Running",
                "progress": f"Processing batch {current_chunk_num} of {total_chunks}...",
                "removed_count": 0
            }))

            prompt = f"""
            You are a strict data cleaner. Below is a JSON list of "intelligence" items.

            **CRITICAL INSTRUCTIONS:**
            1. Aggressively identify concepts that mean the same thing, even if phrased differently.
            2. Merge them into a SINGLE, concise entry.
            3. If two items share >50% conceptual overlap, KEEP ONLY THE BEST ONE.
            4. Your goal is to REDUCE the list size by removing redundancy.
            5. Return ONLY the final JSON list of strings. No markdown, no intro.

            **Input List:**
            {json.dumps(chunk)}
            """

            payload = {
                "messages": [
                    {"role": "system", "content": "You are a data cleaner."},
                    {"role": "user", "content": prompt}
                ],
                "model": "grok-4-fast-reasoning",
                "stream": False,
                "temperature": 0.1
            }

            result = query_xai_api(payload)

            if "error" in result:
                logger.error(f"xAI Error in homogenization chunk {i}: {result['error']}")
                all_cleaned_strings.extend(chunk)
                continue

            try:
                content = result['choices'][0]['message']['content'].strip()
                content = re.sub(r'^```json\s*|\s*```$', '', content, flags=re.MULTILINE)
                cleaned_chunk = json.loads(content)

                if isinstance(cleaned_chunk, list):
                    all_cleaned_strings.extend(cleaned_chunk)
                    logger.info(f"Chunk {i}: Reduced {len(chunk)} -> {len(cleaned_chunk)}")
                else:
                    logger.error(f"Homogenization returned non-list JSON for chunk {i}.")
                    all_cleaned_strings.extend(chunk)

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.error(f"Error parsing homogenization response for chunk {i}: {e}")
                all_cleaned_strings.extend(chunk)

        # Reconstruct Objects with Dates
        final_objects_list = []
        today_str = datetime.now().strftime('%Y-%m-%d')

        for s in all_cleaned_strings:
            s_clean = str(s).strip()
            # If exists in map, reuse date. If not, it's new/merged.
            original_date = content_date_map.get(s_clean)

            final_objects_list.append({
                "content": s_clean,
                "date_added": original_date if original_date else today_str
            })

        final_count = len(final_objects_list)
        removed = total_original - final_count

        logger.info(f"Homogenization complete. Original: {total_original}, Final: {final_count}, Removed: {removed}")

        if removed > 0:
            # Log removed items for debugging (limited to first 3)
            # Since we didn't track *which* items were removed explicitly, we can infer by set difference if they were strings
            # But the list might contain duplicates of the same string.
            # Simple heuristic: Just log that we are updating.
            logger.info(f"Writing updated list to file: {INTELLIGENCE_FILE}")
            try:
                with open(INTELLIGENCE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(final_objects_list, f, indent=4)
                logger.info("File write successful.")
            except Exception as write_err:
                logger.error(f"Failed to write intelligence file: {write_err}")
                raise write_err
        else:
            logger.info("No items removed. File not updated.")

        redis_client.set(HOMOGENIZATION_STATUS_KEY, json.dumps({
            "status": "Complete",
            "removed_count": removed,
            "message": f"Complete! Semantically merged {removed} duplicate ideas."
        }))

        return removed

    except Exception as e:
        logger.error(f"Error in homogenization task: {e}")
        redis_client.set(HOMOGENIZATION_STATUS_KEY, json.dumps({"status": "Error", "message": str(e)}))
        raise e
