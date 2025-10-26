import time
import math
import logging

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages Keepa API tokens, rate limiting, and refills.
    """
    def __init__(self, api_key):
        self.api_key = api_key
        
        # Constants
        self.REFILL_RATE_PER_MINUTE = 5
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 60
        
        # State variables
        self.tokens = 100 # Start with a reasonable guess, will be corrected on first response
        self.max_tokens = 300
        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS
        self.last_refill_timestamp = time.time()

        logger.info("TokenManager initialized without a blocking API call.")

    def _refill_tokens(self):
        """
        Calculates and adds tokens that have been refilled since the last check.
        """
        now = time.time()
        seconds_elapsed = now - self.last_refill_timestamp
        
        if seconds_elapsed > 0:
            refill_amount = (seconds_elapsed / 60) * self.REFILL_RATE_PER_MINUTE
            
            if refill_amount > 0:
                self.tokens = min(self.max_tokens, self.tokens + refill_amount)
                self.last_refill_timestamp = now
                logger.debug(f"Refilled {refill_amount:.2f} tokens. Current tokens: {self.tokens:.2f}")

    def has_enough_tokens(self, estimated_cost):
        """
        Checks if there are enough tokens for a call without waiting.
        Also triggers a refill check.
        """
        self._refill_tokens()
        return self.tokens >= estimated_cost

    def request_permission_for_call(self, estimated_cost):
        """
        Checks if an API call can be made, waits if necessary.
        This is the main public method for controlling API access.
        """
        now = time.time()
        time_since_last_call = now - self.last_api_call_timestamp
        if time_since_last_call < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
            wait_duration = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last_call
            logger.info(f"Rate limit: Pausing for {wait_duration:.2f} seconds.")
            time.sleep(wait_duration)

        self._refill_tokens()

        if self.tokens < estimated_cost:
            tokens_needed = estimated_cost - self.tokens
            if self.REFILL_RATE_PER_MINUTE > 0:
                wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
                logger.warning(
                    f"Insufficient tokens. Have: {self.tokens:.2f}, Need an estimated: {estimated_cost}. "
                    f"Waiting for {wait_time_seconds} seconds to refill."
                )
                time.sleep(wait_time_seconds)
                self._refill_tokens()
            else:
                logger.error("Zero refill rate, cannot wait for tokens. Pausing for 15 minutes as a fallback.")
                time.sleep(900)
                self._refill_tokens()
        
        logger.info(f"Permission granted for API call. Estimated cost: {estimated_cost}. Current tokens: {self.tokens:.2f}")

    def sync_tokens(self):
        """
        Authoritatively fetches the current token status from the Keepa API
        and updates the internal state.
        """
        from .keepa_api import get_token_status
        logger.info("Performing authoritative token sync with Keepa API...")
        status_data = get_token_status(self.api_key)
        if status_data and 'tokensLeft' in status_data:
            self._sync_tokens_from_response(status_data['tokensLeft'])
        else:
            logger.error("Failed to sync tokens. API did not return valid token data.")

    def _sync_tokens_from_response(self, tokens_left_from_api):
        """
        Authoritatively sets the token count from a provided API response value.
        """
        old_token_count = self.tokens
        self.tokens = float(tokens_left_from_api)
        self.last_refill_timestamp = time.time()
        logger.info(
            f"Token count authoritatively synced from API response. "
            f"Previous estimate: {old_token_count:.2f}, New value: {self.tokens:.2f}"
        )

    def update_after_call(self, tokens_left_from_api):
        """
        Updates the token count and timestamp after an API call using the authoritative response.
        """
        self.last_api_call_timestamp = time.time()
        self._sync_tokens_from_response(tokens_left_from_api)