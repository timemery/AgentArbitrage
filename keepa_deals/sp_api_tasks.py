"""
Celery tasks for interacting with the Amazon SP-API and managing user restrictions.
"""

import sqlite3
import logging
from datetime import datetime

# Assuming a shared Celery app instance is available
import os
import httpx
from worker import celery_app as celery
from keepa_deals.amazon_sp_api import check_restrictions
from keepa_deals.db_utils import DB_PATH, get_all_user_credentials

logger = logging.getLogger(__name__)

def _refresh_sp_api_token(refresh_token: str) -> str | None:
    """
    Refreshes the SP-API access token using the refresh token.
    This is a helper function to be used within the Celery task.
    """
    logger.info("Attempting to refresh SP-API access token from within Celery task.")

    client_id = os.getenv("SP_API_CLIENT_ID")
    client_secret = os.getenv("SP_API_CLIENT_SECRET")
    token_url = "https://api.amazon.com/auth/o2/token"

    if not all([client_id, client_secret]):
        logger.error("SP_API_CLIENT_ID or SP_API_CLIENT_SECRET are not configured.")
        return None

    refresh_payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }

    try:
        with httpx.Client() as client:
            response = client.post(token_url, data=refresh_payload)
            response.raise_for_status()
            token_data = response.json()

        new_access_token = token_data.get('access_token')
        if new_access_token:
            logger.info("Successfully refreshed SP-API access token.")
            return new_access_token
        else:
            logger.error("Token refresh response did not contain an access_token.")
            return None
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to refresh SP-API token: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during token refresh: {e}", exc_info=True)
        return None


@celery.task(name='keepa_deals.sp_api_tasks.check_all_restrictions_for_user', bind=True)
def check_all_restrictions_for_user(self, user_id: str, seller_id: str, access_token: str, refresh_token: str):
    """
    Celery task to check restrictions for all existing ASINs for a given user.
    Now accepts tokens directly and handles its own refresh logic.
    """
    logger.info(f"Starting restriction check for all ASINs for user_id: {user_id}")

    try:
        # Ensure we have a valid access token
        if not access_token or access_token == 'manual_placeholder':
            logger.info("Access token missing or placeholder. Attempting to refresh.")
            access_token = _refresh_sp_api_token(refresh_token)
            if not access_token:
                logger.error("Failed to obtain access token via refresh.")
                return "Failed to obtain access token."

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Fetch ASIN and Condition. Order by id DESC (newest first).
            cursor.execute("SELECT ASIN, Condition FROM deals ORDER BY id DESC")
            items = [{'asin': row[0], 'condition': row[1]} for row in cursor.fetchall()]

        if not items:
            logger.warning("No deals found in the database to check.")
            return "No deals to check."

        # Process in batches to provide incremental updates to the UI
        BATCH_SIZE = 5
        total_processed = 0

        for i in range(0, len(items), BATCH_SIZE):
            batch_items = items[i : i + BATCH_SIZE]

            # Use the provided access token for the API calls (chunked)
            results = check_restrictions(batch_items, access_token, seller_id)

            # Save results to the database immediately
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                for asin, result in results.items():
                    cursor.execute("""
                        INSERT OR REPLACE INTO user_restrictions
                        (user_id, asin, is_restricted, approval_url, last_checked_timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        user_id,
                        asin,
                        1 if result['is_restricted'] else 0,
                        result['approval_url'],
                        datetime.utcnow()
                    ))
                conn.commit()

            total_processed += len(results)
            logger.info(f"Progress: Saved restriction data for {total_processed}/{len(items)} ASINs for user_id: {user_id}")

        logger.info(f"Successfully finished restriction check for all {len(items)} ASINs for user_id: {user_id}")

    except sqlite3.Error as e:
        logger.error(f"Database error in check_all_restrictions_for_user: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred in check_all_restrictions_for_user: {e}", exc_info=True)

    return f"Completed restriction check for {len(items)} ASINs for user {user_id}."


@celery.task(name='keepa_deals.sp_api_tasks.check_restriction_for_asins')
def check_restriction_for_asins(asins: list[str]):
    """
    Celery task to check restrictions for a list of new ASINs against all connected users.
    Triggered when new deals are added to the database.
    """
    if not asins:
        return "No new ASINs to check."

    logger.info(f"Starting restriction check for {len(asins)} new ASINs.")

    # Fetch all connected users and their refresh tokens from the database
    user_credentials = get_all_user_credentials()

    if not user_credentials:
        logger.info("No users have connected their SP-API accounts. Skipping restriction check.")
        return "No connected users."

    for creds in user_credentials:
        user_id = creds['user_id']
        refresh_token = creds['refresh_token']

        try:
            # Refresh the access token for the user
            access_token = _refresh_sp_api_token(refresh_token)

            if not access_token:
                logger.warning(f"Could not refresh token for user {user_id}. Skipping.")
                continue

            # Fetch conditions for these ASINs from the database
            items = []
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                placeholders = ', '.join(['?'] * len(asins))
                cursor.execute(f"SELECT ASIN, Condition FROM deals WHERE ASIN IN ({placeholders})", asins)
                items = [{'asin': row[0], 'condition': row[1]} for row in cursor.fetchall()]

            # If some ASINs are missing from DB (shouldn't happen), add them with None condition
            found_asins = {item['asin'] for item in items}
            for asin in asins:
                if asin not in found_asins:
                    items.append({'asin': asin, 'condition': None})

            BATCH_SIZE = 5
            for i in range(0, len(items), BATCH_SIZE):
                batch_items = items[i : i + BATCH_SIZE]
                results = check_restrictions(batch_items, access_token, user_id)

                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    for asin, result in results.items():
                        cursor.execute("""
                            INSERT OR REPLACE INTO user_restrictions
                            (user_id, asin, is_restricted, approval_url, last_checked_timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            user_id,
                            asin,
                            1 if result['is_restricted'] else 0,
                            result['approval_url'],
                            datetime.utcnow()
                        ))
                    conn.commit()

            logger.info(f"Successfully saved restriction data for {len(asins)} new ASINs for user_id: {user_id}")

        except sqlite3.Error as e:
            logger.error(f"Database error in check_restriction_for_asins for user {user_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred in check_restriction_for_asins for user {user_id}: {e}", exc_info=True)

    return f"Completed restriction check for {len(asins)} ASINs for {len(user_credentials)} users."
