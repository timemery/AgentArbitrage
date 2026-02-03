import time
import math
import logging
import os
import redis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages Keepa API tokens, rate limiting, and refills using Redis for shared state.
    """
    REDIS_KEY_TOKENS = "keepa_tokens_left"
    REDIS_KEY_RATE = "keepa_refill_rate"

    def __init__(self, api_key):
        self.api_key = api_key

        # Constants
        self.REFILL_RATE_PER_MINUTE = 5.0 # Default, will be updated from Redis/API
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 60
        self.MIN_TOKEN_THRESHOLD = 50

        # State variables
        self.tokens = 100 # Local cache/fallback
        self.max_tokens = 300
        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS
        self.last_refill_timestamp = time.time()

        # Redis Setup
        redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
        try:
            self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            # Verify connection
            self.redis_client.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}. Falling back to local token management.")
            self.redis_client = None

        logger.info("TokenManager initialized with Redis shared state.")
        # Try to load initial state from Redis
        self._load_state_from_redis()

    def _get_shared_tokens(self):
        if not self.redis_client:
            return None
        try:
            val = self.redis_client.get(self.REDIS_KEY_TOKENS)
            return float(val) if val is not None else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def _set_shared_tokens(self, tokens, rate=None):
        if not self.redis_client:
            return
        try:
            self.redis_client.set(self.REDIS_KEY_TOKENS, str(tokens))
            if rate:
                self.redis_client.set(self.REDIS_KEY_RATE, str(rate))
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    def _load_state_from_redis(self):
        if not self.redis_client:
            return
        try:
            tokens = self._get_shared_tokens()
            if tokens is not None:
                self.tokens = tokens

            rate = self.redis_client.get(self.REDIS_KEY_RATE)
            if rate:
                self.REFILL_RATE_PER_MINUTE = float(rate)
        except Exception as e:
            logger.error(f"Redis load state error: {e}")

    def _refill_tokens(self):
        """
        Calculates and adds tokens that have been refilled since the last check.
        Updates LOCAL state only. Shared state is updated via sync or after-call.
        """
        now = time.time()
        seconds_elapsed = now - self.last_refill_timestamp

        if seconds_elapsed > 0:
            refill_amount = (seconds_elapsed / 60) * self.REFILL_RATE_PER_MINUTE

            if refill_amount > 0:
                self.tokens = min(self.max_tokens, self.tokens + refill_amount)
                self.last_refill_timestamp = now
                # We do NOT push this to Redis to avoid race conditions.
                # Redis is only updated by authoritative API responses or reservations.

    def has_enough_tokens(self, estimated_cost):
        """
        Checks if there are enough tokens for a call without waiting.
        Uses shared state if available.
        """
        shared_tokens = self._get_shared_tokens()
        if shared_tokens is not None:
            self.tokens = shared_tokens
        else:
            self._refill_tokens()

        return self.tokens >= estimated_cost

    def request_permission_for_call(self, estimated_cost):
        """
        Checks if an API call can be made and waits if necessary.
        Reserves tokens in Redis before returning.
        """
        now = time.time()
        time_since_last_call = now - self.last_api_call_timestamp
        if time_since_last_call < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
            wait_duration = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last_call
            logger.info(f"Rate limit: Pausing for {wait_duration:.2f} seconds.")
            time.sleep(wait_duration)

        # 1. Get Fresh State from Redis
        shared_tokens = self._get_shared_tokens()
        if shared_tokens is not None:
            self.tokens = shared_tokens
        else:
            self._refill_tokens()

        wait_time_seconds = 0
        recovery_target = 0

        # --- SYNC CHECK ---
        # If low, force sync with API
        if self.tokens < self.MIN_TOKEN_THRESHOLD:
            logger.info(f"Local/Shared token count ({self.tokens:.2f}) is low. Syncing with Keepa API...")
            self.sync_tokens()
            # self.tokens is now updated from API and saved to Redis

        # --- DECISION LOGIC ---
        if self.tokens <= 0:
            recovery_target = 10
            tokens_needed = recovery_target - self.tokens
            wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
            logger.warning(f"Zero/Neg tokens ({self.tokens:.2f}). Waiting for {wait_time_seconds}s.")

        elif self.tokens < self.MIN_TOKEN_THRESHOLD:
            if estimated_cost <= 10 and self.tokens >= estimated_cost:
                logger.info(f"Priority Pass: allowing small cost {estimated_cost} despite low tokens {self.tokens:.2f}")
            else:
                recovery_target = self.MIN_TOKEN_THRESHOLD + 5
                tokens_needed = recovery_target - self.tokens
                wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
                logger.warning(f"Low tokens ({self.tokens:.2f}). Waiting for {wait_time_seconds}s.")

        # --- WAIT LOOP ---
        if wait_time_seconds > 0:
            if self.REFILL_RATE_PER_MINUTE > 0:
                remaining_wait = wait_time_seconds
                while True:
                    sleep_chunk = max(1, min(remaining_wait, 30))
                    time.sleep(sleep_chunk)

                    # Force sync to get authoritative refill status
                    self.sync_tokens()

                    if self.tokens >= recovery_target:
                         logger.info(f"Tokens recovered ({self.tokens:.2f} >= {recovery_target}). Resuming.")
                         break

                    tokens_needed = recovery_target - self.tokens
                    if tokens_needed <= 0: break

                    new_wait_total = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
                    if new_wait_total > 3600:
                        logger.error("Wait time > 1h. Something wrong.")

                    if new_wait_total != remaining_wait:
                        logger.info(f"Wait update: {self.tokens:.2f}/{recovery_target}. Wait: {new_wait_total}s")
                    remaining_wait = new_wait_total
            else:
                 logger.error("Zero refill rate. Sleeping 15m.")
                 time.sleep(900)
                 self.sync_tokens()

        # --- RESERVATION (Critical Fix) ---
        # We proceed. Deduct estimated cost from Redis immediately to prevent other workers
        # from seeing these tokens as available.
        if self.redis_client:
            try:
                # Use decrby with integer cost (ceil)
                cost_int = math.ceil(estimated_cost)
                new_val = self.redis_client.decrby(self.REDIS_KEY_TOKENS, cost_int)
                self.tokens = float(new_val)
                # logger.info(f"Reserved {cost_int} tokens. New shared balance: {new_val}")
            except Exception as e:
                logger.error(f"Failed to reserve tokens in Redis: {e}")

        logger.info(f"Permission granted. Cost: {estimated_cost}. Current: {self.tokens:.2f}")

    def sync_tokens(self):
        """
        Authoritatively fetches the current token status from the Keepa API
        and updates the internal state and Redis.
        """
        from .keepa_api import get_token_status
        status_data = get_token_status(self.api_key)
        if status_data and 'tokensLeft' in status_data:
            refill_rate = status_data.get('refillRate')
            self._sync_tokens_from_response(status_data['tokensLeft'], refill_rate=refill_rate)
        else:
            logger.error("Failed to sync tokens. API did not return valid token data.")

    def _sync_tokens_from_response(self, tokens_left_from_api, refill_rate=None):
        """
        Authoritatively sets the token count from a provided API response value.
        Updates Redis.
        """
        self.tokens = float(tokens_left_from_api)
        self.last_refill_timestamp = time.time()

        if refill_rate is not None:
            try:
                self.REFILL_RATE_PER_MINUTE = float(refill_rate)
            except (ValueError, TypeError):
                pass

        # Update Redis with authoritative value
        self._set_shared_tokens(self.tokens, self.REFILL_RATE_PER_MINUTE)

    def update_after_call(self, tokens_left_from_api):
        """
        Updates the token count and timestamp after an API call using the authoritative response.
        """
        self.last_api_call_timestamp = time.time()
        self._sync_tokens_from_response(tokens_left_from_api)
