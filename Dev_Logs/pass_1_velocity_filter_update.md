# Pass 1 Velocity Filter Update

Replaced the soft offer-trend penalty with a velocity-aware hard filter and corrected the offer-count fallback chain in `keepa_deals/prime_picks_task.py`. 

## Configuration updates
- Removed `PASS_1_OFFER_TREND_PENALTY_CAP`.
- Added:
  - `PASS_1_OFFER_TREND_RISING_THRESHOLD = 0.25`
  - `PASS_1_OFFER_TREND_VELOCITY_GATE = 100000`
- Updated fallback priority to: `Used_Offer_Count_30_days_avg` -> `Used_Offer_Count_180_days_avg` -> `New_Offer_Count_30_days_avg` -> `New_Offer_Count_180_days_avg`.

## Notes
- To verify the real Pass 2 selection ratio, production deployment is needed because the system requires the xAI API evaluation on real live Amazon data.

## Manual Verification Instructions (Production Environment)
1. Deploy code changes to the production server.
2. Ensure `.env` is loaded.
3. Trigger a Prime Picks refresh from the admin Deals page.
4. Run `python Diagnostics/extract_pass2_reasoning.py celery_worker.log` to evaluate the extraction results.
5. Tail the worker log for `[Pass 1 Filter]` lines and confirm the filter is dropping candidates with rising offers and weak velocity. Ensure that Pass 2 selection ratio improves above 20%.
