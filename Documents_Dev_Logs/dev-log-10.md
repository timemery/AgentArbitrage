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