# keepa_deals/token_manager.py
import time
import math
import logging
from .keepa_api import get_token_status # Import the function to get token status

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages Keepa API tokens, rate limiting, and refills.
    """
    def __init__(self, api_key):
        self.api_key = api_key
        
        # Constants
        self.REFILL_RATE_PER_MINUTE = 5
        # Setting this to a lower value for safety during initialization
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 1
        
        # State variables
        self.tokens = 0
        self.max_tokens = 300 # A default, will be updated from API if possible
        self.last_api_call_timestamp = 0
        self.last_refill_timestamp = time.time()

        # Initialize token count from Keepa
        self._initialize_tokens()

    def _initialize_tokens(self):
        """
        Initializes the token manager by making a cheap API call to get the
        current token count. This prevents the system from making expensive
        calls when the token balance is negative.
        """
        logger.info("Initializing TokenManager by fetching current token status from Keepa...")
        token_data = get_token_status(self.api_key)

        if token_data and 'tokensLeft' in token_data:
            self.tokens = float(token_data['tokensLeft'])
            self.last_api_call_timestamp = time.time()
            self.last_refill_timestamp = time.time()
            logger.info(f"TokenManager initialized successfully. Current tokens: {self.tokens}")
        else:
            # Fallback in case the API call fails during initialization
            logger.error("Failed to fetch initial token status from Keepa. Defaulting to 0 tokens.")
            self.tokens = 0
            self.last_api_call_timestamp = time.time()

        # After initialization, restore the normal rate limit
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 60

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

    def sync_tokens(self, tokens_left_from_api):
        """
        Authoritatively sets the token count from the API response.
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
        Updates the token count and timestamp after an API call.
        """
        self.last_api_call_timestamp = time.time()
        self.sync_tokens(tokens_left_from_api)