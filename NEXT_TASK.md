# Next Task: Fix "Check Restrictions" & Diagnose SP-API Connectivity

## Critical Issue: "Spinning Spinner" & Missing Data
The "Gated" column on the dashboard shows a spinning loading indicator indefinitely for all deals. This persists for hours.
**Key Observation:** Even the fallback URL (which should be generated purely in code if the API fails) is NOT appearing. This suggests the background task `check_all_restrictions_for_user` is failing *completely* before it can write any result to the database, or it is not running at all.

## Objectives

### 1. Verify Task Execution & Failure Point
- **Step 1:** Check `celery_worker.log` (tail -n 200).
    - Do you see `Starting real SP-API restriction check`?
    - Do you see `Missing AWS Credentials` error?
    - Do you see a crash (Stack Trace)?
- **Hypothesis:** The task might be crashing due to an unhandled exception (e.g., Auth failure, missing env var) *before* it gets to the fallback logic.

### 2. Verify Amazon SP-API & AWS Configuration
The user suspects the root cause might be upstream (AWS/Seller Central).
- **Check Environment:** Are `SP_API_AWS_ACCESS_KEY_ID` and `SP_API_AWS_SECRET_KEY` correctly loaded?
- **IAM User:** Does the IAM User for these keys have an attached Policy that allows `execute-api:Invoke`?
- **IAM Role:** Is the IAM User ARN correctly added to the App in Seller Central?
- **App Status:** Is the App in "Draft" state? (Required for "Private" apps).

### 3. Diagnose "No Data Received"
- We need to confirm if we have *ever* successfully received a 200 OK from Amazon.
- **Action:** Run `Diagnostics/diag_test_sp_api.py`.
    - If this script fails, the issue is Credentials/Config.
    - If this script succeeds, the issue is in the `sp_api_tasks.py` logic or Celery integration.

## Technical Context (from previous task)
- **Condition Mapping:** The code now maps "Used - Like New" to `used_like_new` and passes it to the API. This was recently added and *could* be a source of new errors if the mapping is invalid (though unit tests passed).
- **Fallback Logic:** `keepa_deals/amazon_sp_api.py` has logic to set a default URL if `is_restricted` is True. The fact that this isn't showing up implies the code never reaches that line or the DB write fails.

## Files to Investigate
- `keepa_deals/sp_api_tasks.py`: The orchestrator.
- `keepa_deals/amazon_sp_api.py`: The API client.
- `Diagnostics/diag_test_sp_api.py`: The isolation test.
