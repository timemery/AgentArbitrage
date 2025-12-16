import time
import math
import logging

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages Keepa API tokens, rate limiting, and refills.

    STRATEGY UPDATE (Dec 2025):
    This manager implements an "Optimized Controlled Deficit" strategy.

    1.  **Hard Stop at Zero:** We never make a call if the balance is <= 0.
    2.  **Controlled Deficit:** Keepa allows the balance to go negative as long as the
        starting balance was positive. We leverage this to avoid long pauses.
        If we have enough tokens to be above `MIN_TOKEN_THRESHOLD` (e.g., 50),
        we allow the call to proceed even if `estimated_cost > current_tokens`.
        This prevents the system from pausing for ~18 minutes to refill to max just
        because it is slightly short of the estimated cost.
    3.  **Smart Refill Waits:** When we DO need to wait (because we are below the threshold),
        we wait only until we reach `MIN_TOKEN_THRESHOLD + buffer`. We do NOT wait
        for `max_tokens`. This keeps the system running with minimal downtime.
    """
    def __init__(self, api_key):
        self.api_key = api_key
        
        # Constants
        self.REFILL_RATE_PER_MINUTE = 5
        # 60-second polling interval / rate limit to prevent flooding the API
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 60
        # The safety buffer. If we have more than this, we act aggressively (allow deficit).
        # If less, we pause to recover to this level.
        self.MIN_TOKEN_THRESHOLD = 50
        
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
        Checks if an API call can be made and waits if necessary.

        This method handles two types of limits:
        1. Frequency Limit (60 seconds between calls).
        2. Token Cost Limit (Keepa API quotas).
        """
        now = time.time()
        time_since_last_call = now - self.last_api_call_timestamp

        # --- FREQUENCY LIMIT CHECK ---
        # This ensures we don't hit the API too rapidly, regardless of token balance.
        # This is a fixed 60-second window.
        if time_since_last_call < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
            wait_duration = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last_call
            logger.info(f"Rate limit: Pausing for {wait_duration:.2f} seconds.")
            time.sleep(wait_duration)

        self._refill_tokens()

        wait_time_seconds = 0

        # --- TOKEN COST LIMIT CHECK ---
        # Refined Strategy: Avoid "Wait to Max" behavior.

        if self.tokens <= 0:
            # Hard stop: Must wait to get back to a positive balance.
            # We wait to reach the threshold to prevent immediate subsequent waiting.
            tokens_needed = self.MIN_TOKEN_THRESHOLD - self.tokens
            wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
            logger.warning(
                f"Zero or negative tokens. Have: {self.tokens:.2f}. "
                f"Waiting for {wait_time_seconds} seconds to refill to threshold ({self.MIN_TOKEN_THRESHOLD})."
            )
        elif self.tokens < estimated_cost:
            # Check if we are above the aggressive threshold
            if self.tokens > self.MIN_TOKEN_THRESHOLD:
                # OPTIMIZATION: We have enough buffer to proceed safely.
                # We intentionally allow the balance to dip negative (Deficit Spending).
                # This avoids the previous behavior of waiting ~18 minutes to refill to 300
                # just because we were slightly short.
                logger.info(
                    f"Tokens ({self.tokens:.2f}) > Threshold ({self.MIN_TOKEN_THRESHOLD}). "
                    f"Allowing call despite estimated cost ({estimated_cost})."
                )
            else:
                # We are low on tokens. We need to wait.
                # REFINEMENT: Instead of waiting for max_tokens (which takes forever),
                # we only wait until we are back to our "safe operating level" (MIN_TOKEN_THRESHOLD).
                target_tokens = self.MIN_TOKEN_THRESHOLD + 5
                tokens_needed = target_tokens - self.tokens
                wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
                logger.warning(
                    f"Insufficient tokens (<{self.MIN_TOKEN_THRESHOLD}). Have: {self.tokens:.2f}, Need: {estimated_cost}. "
                    f"Waiting for {wait_time_seconds} seconds to refill to target ({target_tokens})."
                )

        if wait_time_seconds > 0:
            if self.REFILL_RATE_PER_MINUTE > 0:
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
