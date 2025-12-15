
import sqlite3
import os
import logging
from keepa_deals.db_utils import (
    create_deals_table_if_not_exists,
    create_user_credentials_table_if_not_exists,
    create_user_restrictions_table_if_not_exists,
    save_user_credentials,
    DB_PATH
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_test_db():
    """Initializes the test database and inserts necessary data."""
    logger.info("Initializing database schema...")

    # Initialize tables
    create_deals_table_if_not_exists()
    create_user_credentials_table_if_not_exists()
    create_user_restrictions_table_if_not_exists()

    # Insert test credentials (using a dummy refresh token for now, as we can't generate a real one easily without OAuth flow)
    # However, the diagnostic script *might* need a valid refresh token if it tries to hit the real API.
    # The prompt implies I should use the environment credentials.
    # But SP-API auth flow requires a refresh token to get an access token.
    # The .env file has Client ID/Secret, AWS Keys, but NOT a refresh token.
    # Wait, the user prompt says: "A manual SP-API credential entry form (Seller ID and Refresh Token) is available... and persists credentials to the `user_credentials` table"
    # This implies the user has to input it.
    # But for DIAGNOSIS, maybe I can use a placeholder if I'm just testing the *code logic* or if I have a refresh token?
    # Actually, the user wants to "Diagnose SP-API Connectivity".
    # Without a valid refresh token, I can't get an access token, so I can't call the API.
    # I'll check if the diagnostic script allows manual token entry or if it just fails.
    # The error "No user credentials found" confirms it needs *something* in the DB.

    # I will insert a dummy user. If the diagnostic script fails on "Invalid Refresh Token", that's a valid finding.
    # But if I want to test "Connectivity", I need valid creds.
    # Since I don't have a refresh token in .env, I can't fully test the *auth* flow unless I mock it or if there is a way to generate one (unlikely without user interaction).
    # However, the user asked to "Check Environment".
    # I will insert a dummy record to bypass the "No user credentials found" error and see what happens next.

    dummy_user_id = "TEST_USER"
    dummy_refresh_token = "dummy_refresh_token_123"

    logger.info(f"Inserting dummy credentials for user: {dummy_user_id}")
    save_user_credentials(dummy_user_id, dummy_refresh_token)

    # I also need some deals in the DB to test the restriction check loop if the script does that.
    # The diagnostic script seems to check connectivity first.

    logger.info("Database setup complete.")

if __name__ == "__main__":
    setup_test_db()
