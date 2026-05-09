# Dev Log: Prime Picks Pass 1 Scoring - Offer-Trend Awareness

**Date:** 2026-05-09
**Task Overview:**
The goal of this task was to update the Pass 1 (Smart Floor) Time Decay scoring formula in `keepa_deals/prime_picks_task.py`. The Pass 2 xAI Mastermind was frequently rejecting candidates due to rising offer counts (a sign of imminent price erosion). Since Pass 1 did not weight offer trends, it was sending suboptimal candidates to Pass 2, resulting in a low selection ratio (4 out of 20, or 20%). The objective was to penalize candidates with rising offer counts and slightly reward those with stable or falling counts, pre-aligning Pass 1's top candidates with Pass 2's reasoning.

**Challenges Faced:**
1. **Determining the Correct Column:** The request mentioned using the 30-day average offer count but the exact SQLite column name was not explicitly known.
2. **Prioritizing "New" vs. "Used" Offers:** Since this is an Amazon Arbitrage application, new offers are usually the primary driver of competition, so deciding which metric to prioritize was important for the logic.
3. **Verification in Sandbox:** The task required verifying the new Pass 2 selection ratio. However, my isolated sandbox environment lacked the production `celery_worker.log` data and populated `deals.db` to produce meaningful runtime statistics.

**What was done to address them:**
1. I used the existing `sanitize_col_name` function from `keepa_deals.db_utils` to convert the human-readable headers ("New Offer Count - 30 days avg." and "Used Offer Count - 30 days avg.") into their exact database column equivalents: `New_Offer_Count_30_days_avg` and `Used_Offer_Count_30_days_avg`.
2. I implemented a fallback logic that prioritizes the "New" 30-day average offer count over the "Used" average. This is because "New" condition items are the standard for Retail/Online Arbitrage competition.
3. I added configurable constants to the top of `keepa_deals/prime_picks_task.py`:
   - `PASS_1_OFFER_TREND_PENALTY_CAP = 0.5`
   - `PASS_1_OFFER_TREND_BONUS_MULTIPLIER = 1.1`
4. I updated the scoring loop in `generate_prime_picks` to calculate the `offer_trend` (current offers vs. 30-day average). A positive trend applies a dynamic penalty `max(0.5, 1.0 / (1.0 + offer_trend))`, while a non-positive trend applies a flat `1.1` multiplier bonus.
5. Because I could not execute a meaningful verification in the sandbox, I detailed explicit manual instructions in a `dev_log.txt` (and also within this log) for the system administrator to verify the effect in the live production environment using the existing diagnostic script `Diagnostics/extract_pass2_reasoning.py`.

**Success Status:**
The code implementation and testing was **Successful**. The logic safely applies the desired penalties and bonuses without causing regressions in the core test suite (`./run_tests.sh` passed). The final Pass 2 selection ratio increase remains to be confirmed by the human admin in production following the provided instructions.

**Production Verification Instructions (For Admin):**
1. Log in to the application as an admin.
2. Go to the Deals page and trigger a Prime Picks refresh.
3. Access the VPS server (agentarbitrage.co) via SSH.
4. Run the diagnostic script against the celery worker log:
   `python3 Diagnostics/extract_pass2_reasoning.py celery_worker.log`
5. Verify that the Pass 2 selection ratio is higher than 20%.
