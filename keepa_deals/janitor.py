from worker import celery_app as celery
from .db_utils import DB_PATH
import sqlite3
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

def _clean_stale_deals_logic(grace_period_hours):
    """
    Core logic for cleaning stale deals.
    """
    cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=grace_period_hours)).isoformat()
    logger.info(f"Janitor: Starting cleanup. Deleting deals older than {cutoff_time}...")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Count before deleting for logging
            cursor.execute("SELECT COUNT(*) FROM deals WHERE last_seen_utc < ?", (cutoff_time,))
            to_delete_count = cursor.fetchone()[0]

            if to_delete_count > 0:
                cursor.execute("DELETE FROM deals WHERE last_seen_utc < ?", (cutoff_time,))
                conn.commit()
                logger.info(f"Janitor: Successfully deleted {to_delete_count} stale deals.")

                # Optional: VACUUM if many deletions occurred (e.g., > 1000)
                if to_delete_count > 1000:
                    logger.info("Janitor: Performing VACUUM to reclaim space...")
                    cursor.execute("VACUUM")
                    logger.info("Janitor: VACUUM complete.")
            else:
                logger.info("Janitor: No stale deals found.")

            return to_delete_count

    except Exception as e:
        logger.error(f"Janitor failed: {e}", exc_info=True)
        return 0

@celery.task(name='keepa_deals.janitor.clean_stale_deals')
def clean_stale_deals(grace_period_hours=72):
    """
    Deletes deals that haven't been seen/updated for a specified period (default 72 hours).
    This helps keep the database size manageable and removes "dead" deals that are no longer
    appearing in Keepa results.
    """
    return _clean_stale_deals_logic(grace_period_hours)
