# Verification Instructions for Issue: Pass 1 Offer-Trend De-duplication

To verify the changes in production since the dev environment differs, please perform the following steps:

1. **Trigger a Prime Picks Refresh:**
   Log into the admin Deals page on the live production server (agentarbitrage.co) and click the 'Refresh Prime Picks' button.

2. **Extract Pass 2 Reasoning:**
   Run the `Diagnostics/extract_pass2_reasoning.py` script against the production `celery_worker.log`:
   `python Diagnostics/extract_pass2_reasoning.py`

3. **Confirm the Following in the Log:**
   - The new "[Pass 1 Filter]" log lines appear with non-zero drop counts. E.g.:
     `[Pass 1 Filter] Offer-trend filter dropped N of M candidates; K had no trend signal`
   - The "[Pass 1 Filter] No trend signal for ASIN=XXX" log line should only appear at a low rate.
   - The Pass 2 selection ratio improves above 20% (e.g., > 4 out of 20).
   - Rejected candidates in the Pass 2 reasoning output no longer cite "increasing offers" as the dominant rejection reason for deals with a sales rank > 1M. Any deals remaining with rising offers should be for ranks under 100k, where Pass 2 has different logic.
   - The textbook counterfeit risk override remains effective.
