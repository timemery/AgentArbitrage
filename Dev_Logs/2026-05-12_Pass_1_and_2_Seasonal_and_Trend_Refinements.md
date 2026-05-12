# Dev Log: Pass 1 and Pass 2 Seasonal and Trend Refinements
**Date:** 2026-05-12

## Task Overview
The goal of this multi-part task was to refine the Prime Picks deal filtering pipeline to be more accurate and strategically sound.
1. **Pass 1 Offer-Trend Filter Fix:** In `keepa_deals/new_analytics.py`, the offer-trend deduplication function (`get_offer_count_trend_from_flat`) was updated to compare `Used_Offer_Count_Current` against `Used_Offer_Count_365_days_avg` instead of the 30-day average, since the 30-day column is intentionally left NULL by the Smart Ingestor to optimize token usage.
2. **Pass 1 Year-Round Velocity Cap:** In `keepa_deals/prime_picks_task.py`, a new hard filter (`PASS_1_YEAR_ROUND_VELOCITY_CAP = 2000000`) was introduced to drop candidates explicitly categorized as "Year-round" if their sales rank exceeds 2,000,000, filtering out structurally poor non-seasonal candidates. Seasonal candidates were intentionally exempted from this cap.
3. **Pass 2 Seasonal Reasoning Correction:** In `keepa_deals/prime_picks_task.py`, a new prompt block (`SEASONAL HIGH-RANK CORRECTION`) was appended to the Pass 2 Mastermind LLM prompt. This instructs the AI to not reject valid seasonal items solely because of high current (off-season) sales rank, recognizing that off-season buys present a highly lucrative arbitrage opportunity if stored in a prep center.

## Challenges Faced
- Understanding the database structure regarding offer count columns: It was discovered that short-term window columns (30/60/90/180) are intentionally kept NULL to save tokens. Relying on the 365-day average required renaming local variables and docstring updates to reflect the new logic.
- Balancing Pass 1 and Pass 2 capabilities: We had to be extremely careful to drop structurally weak deals in Pass 1 (Year-round items with >2M rank) without accidentally dropping seasonal items that legitimately have a temporary high rank.
- Modifying the LLM prompt needed exact, precise wording to override its general assumption that high sales rank implies a bad deal, without conflicting with the existing textbook counterfeit risk block.
- **Production Server Note:** The live `agentarbitrage.conf` apache file in `/etc/apache2/sites-enabled/` has the `WSGIApplicationGroup %{GLOBAL}` directive that is not reflected in the repo. This required keeping in mind that any future Apache config changes require syncing from the live server first. No deploy changes deviated from the normal `./deploy_update.sh` after SFTP.

## Actions Taken
- **`keepa_deals/new_analytics.py`**: Swapped `Used_Offer_Count_30_days_avg` with `Used_Offer_Count_365_days_avg` inside `get_offer_count_trend_from_flat`, renamed variables (`avg30` -> `avg365`), and updated the docstring.
- **`keepa_deals/prime_picks_task.py`**: Added `PASS_1_YEAR_ROUND_VELOCITY_CAP = 2000000`. Inside `generate_prime_picks`, added logic to evaluate `deal.get('Detailed_Seasonality', '')` and the `sales_rank`. If it matched 'year-round' and the rank was over 2M, it flagged `drop_candidate = True` and incremented `dropped_year_round_high_rank`.
- **`keepa_deals/prime_picks_task.py`**: Updated the Pass 1 log message to print `dropped_year_round_high_rank`. Appended the "SEASONAL HIGH-RANK CORRECTION" exact text block into the `prompt` string sent to xAI.

## Task Result
**Successful.** The test suite executed cleanly with no errors, and the logic was verified via static code review. All conditions specified by the user were implemented exactly as requested.