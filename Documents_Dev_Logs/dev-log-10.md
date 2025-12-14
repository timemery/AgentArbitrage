# Dev Log 10: Fixing SP-API Restrictions & Authentication

## Overview
This sprint focused on fixing the "Check Restrictions" feature on the dashboard, which was previously non-functional (stuck loading) or erroring out. The root causes were identified as missing AWS Signature Version 4 (SigV4) signing for API requests and missing configuration keys. We also implemented a fallback mechanism for "Apply" links to prevent 404 errors.

## Critical Changes

### 1. SP-API Authentication (SigV4)
- **Problem:** The previous implementation relied solely on the Login with Amazon (LWA) access token. However, the `getRestrictions` operation (and most SP-API calls) requires requests to be signed using AWS Signature Version 4 (SigV4) with IAM credentials. This caused all requests to fail with `403 Forbidden`.
- **Fix:** 
    - Replaced the `httpx` client in `keepa_deals/amazon_sp_api.py` with `requests` combined with `requests-aws4auth`.
    - Implemented logic to read `SP_API_AWS_ACCESS_KEY_ID` and `SP_API_AWS_SECRET_KEY` from the environment and sign every request.
    - Added `requests-aws4auth` to `requirements.txt`.

### 2. URL Fallback Logic ("Apply" Buttons)
- **Problem:** Even when the API worked, the "Apply" buttons on the dashboard often linked to `.../null` (resulting in a 404). This happened because Amazon's API does not always return a specific "one-click" approval deep link.
- **Fix:** Updated `keepa_deals/amazon_sp_api.py` to implement a fallback strategy:
    - If `is_restricted` is `True`, the `approval_url` defaults to `https://sellercentral.amazon.com/product-search/search?q={ASIN}`.
    - If a specific deep link is found in the API response, it overwrites the default.
    - This ensures the user is always directed to a valid page where they can request approval.

### 3. Performance & Stability
- **Batching:** Refactored the `check_all_restrictions_for_user` task in `keepa_deals/sp_api_tasks.py`. It now processes ASINs in batches of 5 (instead of all at once) and commits to the database incrementally. This prevents long database locks and allows the dashboard UI to update progressively as the background task runs.
- **Configuration Alert:** Modified `wsgi_handler.py` and `templates/settings.html` to check for the presence of the required AWS keys. If missing, a prominent red alert is displayed on the Settings page with instructions.

## Verification
- **Test Scripts:** Created `test_sp_api_fallback.py` to verify the URL generation logic handles both "missing link" and "specific link" scenarios correctly.
- **Frontend:** Verified that the "Missing AWS Keys" alert appears when keys are absent and disappears when they are present.
- **Integration:** Verified that the system now correctly identifies restricted items and saves the status to the `user_restrictions` table.

## Next Steps for Validation
1.  **Monitor Reset:** The database is currently being reset (`--reset`) to clear out old `null` links.
2.  **Verify Data Population:** Watch the `user_restrictions` table (or the dashboard "Gated" column) to ensure it populates with valid URLs (no `null`s).
3.  **Token Management:** The system will report `429` errors and pause when tokens are exhausted. This is expected behavior.

## Technical Details
- **Files Modified:**
    - `keepa_deals/amazon_sp_api.py`
    - `keepa_deals/sp_api_tasks.py`
    - `wsgi_handler.py`
    - `templates/settings.html`
    - `requirements.txt`

# Dev Log 11: Token Stabilization, Upserter Optimization & Restrictions Fallback

## Overview

This sprint focused on two critical stability issues: a "race condition" causing compounding token exhaustion, and a regression in the data collection logic that was wasting API resources. We also implemented a safety fallback for the "Check Restrictions" feature to ensure "Apply" buttons always function, even when the API returns incomplete data.

## Challenges & Diagnoses

### 1. The Token Race Condition

- **Symptom:** The system would enter a "death spiral" where the Keepa token balance could never recover, eventually pausing all data collection.
- **Root Cause:** The `simple_task.py` (Upserter), which runs every minute, was configured to run as long as *any* tokens (>5) were available. It was effectively "stealing" the small trickle of refilled tokens that the `backfiller.py` (Backfiller) was waiting for. Since the Backfiller waits for a full bucket refill (300 tokens) once it hits a deficit, the Upserter kept draining the bucket before the Backfiller could ever resume.
- **Diagnosis:** The token management system didn't account for two concurrent high-consumption processes competing for the same limited resource pool.

### 2. The "100 Seller IDs" Regression

- **Symptom:** Logs showed `simple_task.py` attempting to "fetch seller data for 100 seller IDs" per batch.
- **Root Cause:** While the Backfiller had been optimized to fetch only the *single* winning seller per deal, the Upserter had not received this update. It was still fetching data for *every* seller across *every* offer in the batch, resulting in massive, wasteful API calls (e.g., 20x higher load than necessary).

### 3. "Check Restrictions" Broken Links

- **Symptom:** The "Apply" button on the dashboard linked to `.../null`.
- **Root Cause:** The Amazon SP-API `getListingsRestrictions` operation often returns a "Restricted" status without providing a specific approval workflow link. This happens because our current request is generic (checking the ASIN only) rather than specific (checking ASIN + Condition). Without a link from the API, the UI had nowhere to go.

## Solutions Implemented

### 1. Token Stabilization Strategy

- **Increased Safety Buffer:** Updated `simple_task.py` to require a minimum of **20 tokens** (up from 5) before executing. This acts as a "safety valve," ensuring the Upserter only runs when there is a healthy surplus, leaving the "dregs" for the Backfiller or allowing the bucket to refill.
- **Slowed Backfill Rate:** Reverted `DEALS_PER_CHUNK` in `backfiller.py` from 5 to **20**. Processing larger chunks takes longer, introducing a natural delay that allows more tokens to refill between API calls.
- **Forced Sync:** Added `token_manager.sync_tokens()` to the startup of `simple_task.py` to ensure it always makes decisions based on the authoritative token count from the API.

### 2. Logic Optimization

- **Aligned Seller Fetching:** Refactored `simple_task.py` to use `get_seller_info_for_single_deal`. It now identifies the single lowest-priced "Used" offer and fetches data *only* for that seller. This eliminated the wasteful bulk fetching entirely.

### 3. Restrictions Fallback

- **Generic URL Generation:** Updated `keepa_deals/amazon_sp_api.py` to implement a fallback. If the API returns a restriction but no deep link, the system now generates a valid URL to the Seller Central "Add Product" search page (`https://sellercentral.amazon.com/product-search/search?q={ASIN}`). This allows the user to manually start the approval process instead of hitting a dead link.

## Outcome

The system is now protected against the race condition that was draining tokens. The upserter task is significantly more efficient, consuming fewer tokens per run. The "Check Restrictions" feature is functional and fails gracefully to a manual search page when specific links are unavailable.

## Known Limitations / Next Steps

- **Generic Restrictions:** The restriction check is still "generic." To get specific "One-Click Apply" links from Amazon, we must update the API call to pass the specific `conditionType` (e.g., `used_like_new`) of the deal. This has been documented for a future task.