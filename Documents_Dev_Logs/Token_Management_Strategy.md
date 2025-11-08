# Token Management Strategy for Keepa API

This document outlines the "controlled deficit" strategy implemented in the `TokenManager` class (`keepa_deals/token_manager.py`) to handle the specific rate-limiting behavior of the Keepa API.

## 1. The Problem: Indefinite Stalls

The `backfill_deals` Celery task was experiencing indefinite stalls. The logs would show the worker pausing to wait for a number of tokens that was greater than the maximum capacity of the token bucket (e.g., needing 450 tokens when the max is 300). This caused the process to wait forever.

The root cause was a misunderstanding of the Keepa API's token rules. The initial logic in `TokenManager` was too cautious and operated on a flawed assumption:

**Flawed Assumption:** An API call cannot proceed if its estimated cost is greater than the current number of available tokens.

This led to the `TokenManager` pausing the script to wait for a token level that could never be reached, resulting in a permanent stall.

## 2. The Key Finding: Negative Balances are Allowed

After a thorough review of the official Keepa API documentation (specifically the "Product Finder" section of `Keepa_Documentation-official-2.md`), the actual rule was discovered:

> **Note:** All API requests execute regardless of your current token balance, **as long as it’s positive.** Requesting large result sets may cause your token balance to go negative. Use with caution!

This means the only hard rule for making an API call is that the token balance must be `> 0`. The API is designed to allow expensive calls to drive the balance into a negative value.

## 3. The Solution: The "Controlled Deficit" Strategy

Based on this finding, a new, more robust strategy was implemented in the `request_permission_for_call` method of the `TokenManager`.

The strategy works as follows:

1.  **Hard Stop at Zero:** If the current token balance is `<= 0`, the system **must** wait. It calculates the time needed to refill to at least 1 token and pauses execution for that duration.

2.  **The Controlled Deficit:** If the token balance is positive (`> 0`) but the `estimated_cost` of the next call is greater than the available tokens, the system does **not** proceed immediately. While the API allows it, making a very expensive call with a very low token balance risks hitting an unknown maximum deficit limit. Instead, the `TokenManager` takes a safer, more efficient approach: it proactively waits until the token bucket is **completely full** (i.e., reaches `max_tokens`, which is 300).

3.  **Proceed with a Full Bucket:** Once the bucket is full, the `TokenManager` grants permission for the expensive call to proceed. This allows the call to create a small, predictable, and safe negative balance (e.g., starting at 300, a 400-token call results in a -100 balance). This deficit is then recovered during the next wait cycle.

This strategy ensures the process never stalls while also preventing it from accumulating an excessively large and potentially risky token deficit.

## 4. The Role of `MAX_ASINS_PER_BATCH`

The `MAX_ASINS_PER_BATCH` constant in `keepa_deals/backfiller.py` is a critical part of this strategy. Its value is set to a conservative number (e.g., 20) to ensure that the estimated cost of a single batch call remains close to the maximum token capacity.

*   `Estimated Cost = 15 tokens/ASIN * 20 ASINs = 300 tokens`

By keeping the estimated cost near the bucket's maximum, we ensure that the potential token deficit on any given call is minimized, further enhancing the stability and predictability of the system. This value should not be increased without careful consideration of the impact on the "controlled deficit" strategy.
