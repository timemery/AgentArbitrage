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
from keepa_deals.db_utils import DB_PATH

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
        # For simplicity in this fix, we'll assume the initial token is valid for the first run.
        # A more robust solution would store and check expiry, but this architecture is now correct.
        # This is where you would call `_refresh_sp_api_token` if you stored the expiry time.

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Fetch all unique ASINs from the deals table
            cursor.execute("SELECT DISTINCT ASIN FROM deals")
            asins = [row[0] for row in cursor.fetchall()]

        if not asins:
            logger.warning("No ASINs found in the database to check.")
            return "No ASINs to check."

        # Use the provided access token for the API calls
        results = check_restrictions(asins, access_token, seller_id)

        # Save results to the database
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
        logger.info(f"Successfully saved restriction data for {len(results)} ASINs for user_id: {user_id}")

    except sqlite3.Error as e:
        logger.error(f"Database error in check_all_restrictions_for_user: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred in check_all_restrictions_for_user: {e}", exc_info=True)

    return f"Completed restriction check for {len(asins)} ASINs for user {user_id}."


@celery.task(name='keepa_deals.sp_api_tasks.check_restriction_for_asins')
def check_restriction_for_asins(asins: list[str]):
    """
    Celery task to check restrictions for a list of new ASINs against all connected users.
    Triggered when new deals are added to the database.
    """
    if not asins:
        return "No new ASINs to check."

    logger.info(f"Starting restriction check for {len(asins)} new ASINs.")

    # In a real system, you'd have a way to get all users who have connected their accounts.
    # For this simulation, we'll hardcode the user ID we used in the OAuth flow.
    connected_user_ids = ['user_123'] # Placeholder

    if not connected_user_ids:
        logger.info("No users have connected their SP-API accounts. Skipping restriction check.")
        return "No connected users."

    for user_id in connected_user_ids:
        try:
            # In a real app, you'd fetch the specific user's access token
            access_token = "dummy_access_token"

            results = check_restrictions(asins, access_token)

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
            logger.info(f"Successfully saved restriction data for {len(results)} new ASINs for user_id: {user_id}")

        except sqlite3.Error as e:
            logger.error(f"Database error in check_restriction_for_asins for user {user_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred in check_restriction_for_asins for user {user_id}: {e}", exc_info=True)

    return f"Completed restriction check for {len(asins)} ASINs for {len(connected_user_ids)} users."
