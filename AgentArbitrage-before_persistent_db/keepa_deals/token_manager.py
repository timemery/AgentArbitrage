# keepa_deals/token_manager.py
import time
import math
import logging
from .keepa_api import get_token_status

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
        self.tokens = 0
        self.max_tokens = 300 # A default, will be updated from API if possible
        self.last_api_call_timestamp = 0
        self.last_refill_timestamp = time.time()

        # Initialize token count from Keepa
        self._initialize_tokens()

    def _initialize_tokens(self):
        """
        Initializes token manager without an API call to avoid hanging issues.
        The token count will be synced on the first API response.
        """
        logger.info("Initializing TokenManager with default values. Token count will be synced after the first API call.")
        self.tokens = 100  # Start with a reasonable guess, will be corrected on first response
        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS
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

    def request_permission_for_call(self, estimated_cost):
        """
        Checks if an API call can be made, waits if necessary.
        This is the main public method for controlling API access.
        """
        # 1. Enforce time-based rate limit
        now = time.time()
        time_since_last_call = now - self.last_api_call_timestamp
        if time_since_last_call < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
            wait_duration = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last_call
            logger.info(f"Rate limit: Pausing for {wait_duration:.2f} seconds.")
            time.sleep(wait_duration)

        # 2. Update token count with any refills that occurred
        self._refill_tokens()

        # 3. Check if we have enough tokens and wait if we don't
        if self.tokens < estimated_cost:
            tokens_needed = estimated_cost - self.tokens
            if self.REFILL_RATE_PER_MINUTE > 0:
                # Calculate the minimum time required to get enough tokens
                wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
                logger.warning(
                    f"Insufficient tokens. Have: {self.tokens:.2f}, Need an estimated: {estimated_cost}. "
                    f"Waiting for {wait_time_seconds} seconds to refill."
                )
                time.sleep(wait_time_seconds)
                # Refill tokens again after waiting
                self._refill_tokens()
            else:
                # This case should not happen with a positive refill rate, but as a fallback.
                logger.error("Zero refill rate, cannot wait for tokens. Pausing for 15 minutes as a fallback.")
                time.sleep(900)
                self._refill_tokens()
        
        logger.info(f"Permission granted for API call. Estimated cost: {estimated_cost}. Current tokens: {self.tokens:.2f}")
        # The actual deduction will happen after the call, using update_from_response

    def update_after_call(self, tokens_consumed):
        """
        Updates the token count after an API call using the authoritative cost.
        """
        self.last_api_call_timestamp = time.time()
        self.tokens -= tokens_consumed
        logger.info(f"Updated token count after API call. Consumed: {tokens_consumed}. Tokens remaining: {self.tokens:.2f}")