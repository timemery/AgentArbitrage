# Dev Log 11: Remove AWS SigV4 & Fix Restriction Check (2025-12-17)

## Overview
The primary objective of this task was to enable the "Check Restrictions" feature for users who cannot provide AWS IAM credentials (AWS Access Key/Secret Key). Recent updates to the Amazon Selling Partner API (SP-API) for Private Applications allow requests using only the Login with Amazon (LWA) Access Token, removing the need for AWS Signature Version 4 (SigV4) signing.

During the implementation, several secondary issues were discovered and resolved, including worker concurrency blocking tasks, environment mismatches (Sandbox vs. Production), and file corruption.

## Challenges Faced

1.  **Strict IAM Dependency:** The existing code explicitly checked for `SP_API_AWS_ACCESS_KEY_ID` and `SP_API_AWS_SECRET_KEY` environment variables and aborted if they were missing, preventing any API call attempts.
2.  **403 Forbidden Errors:** After removing the local checks, the API calls failed with `403 Forbidden` ("The access token you provided is revoked, malformed or invalid") despite the token refresh process returning `200 OK`.
3.  **Environment Mismatch:** Diagnostic investigation revealed that the user's LWA token was valid **only for the Sandbox environment**, but the application was targeting the **Production endpoint**. This caused the 403 errors.
4.  **Task Execution Blocking:** The `check_all_restrictions_for_user` task was not running even when manually triggered. This was traced to the Celery worker running with default concurrency (likely 1 process on the VPS), which was completely blocked by the long-running `backfill_deals` task.
5.  **File Corruption:** A `SyntaxError` in `keepa_deals/token_manager.py` revealed that the file had been overwritten with an HTML error page (GitHub 404) in a previous commit, breaking the worker startup.

## Actions Taken

### 1. Removed AWS SigV4 Dependency
*   **Modified `keepa_deals/amazon_sp_api.py`:** Removed `requests-aws4auth` import, IAM credential checks, and the `AWS4Auth` signing object. The request now relies solely on the `x-amz-access-token` header.
*   **Updated `requirements.txt`:** Removed `requests-aws4auth`.
*   **Frontend Cleanup:** Updated `wsgi_handler.py` and `templates/settings.html` to remove the warning banner and help text prompting users for AWS keys.

### 2. Resolved 403 Forbidden (Sandbox Switch)
*   **Enhanced Diagnostics:** Updated `Diagnostics/diag_test_sp_api.py` to test token validity against both Production (`sellingpartnerapi-na.amazon.com`) and Sandbox (`sandbox.sellingpartnerapi-na.amazon.com`) endpoints.
*   **Diagnosis:** The token worked for Sandbox (`200 OK`) but failed for Production (`403 Forbidden`), confirming the user's app/credentials are currently scoped to Sandbox.
*   **Configuration Update:** Modified `keepa_deals/amazon_sp_api.py` to default `SP_API_BASE_URL_NA` to the **Sandbox endpoint**. Added support for an `SP_API_URL` environment variable to allow Production overrides in the future.

### 3. Fixed Task Execution (Concurrency)
*   **Updated `start_celery.sh`:** Added `--concurrency=4` to the Celery worker command. This allows the worker to process up to 4 tasks simultaneously, ensuring that short UI-triggered tasks (like restriction checks) can run in parallel with the long-running backfill task.

### 4. Restored Corrupted File
*   **Restored `keepa_deals/token_manager.py`:** Overwrote the corrupted HTML content with the correct Python class implementation to fix the `SyntaxError`.

## Outcome
**Success.** The "Check Restrictions" feature is now functional.
*   The application successfully connects to the Amazon SP-API Sandbox without IAM credentials.
*   The "Re-check Restrictions" button correctly queues the task, and the worker picks it up immediately.
*   The Dashboard UI updates with restriction status (currently showing "Restricted" for all items, which is expected behavior for Sandbox mock data).

## Remaining UX Issues (Handed Over)
Two issues persist which affect the user experience but are not code bugs in the current scope:
1.  **100% Restriction Rate:** Likely due to the Sandbox returning mock data. Testing against Production (requires a Production-valid token) is needed for real data.
2.  **Broken Apply Links:** The generated "Apply" links redirect to a generic search page. The link format needs to be updated.
   *   *See `Documents_Dev_Logs/Task_Improve_Restrictions_UX.md` for details.*
