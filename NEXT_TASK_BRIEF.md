# Recommended Next Steps: Resolve Dwindling Deals

**Status:** A critical flaw in the "List at" price calculation logic has been identified, where a fallback mechanism is populating invalid prices ("Zombie Listings") which are then rejected by the AI Reasonableness Check. This, combined with a broad Keepa Query, causes the system to reject ~95% of deals, leading to a dwindling database as the Janitor deletes old records.

## Objective
Fix the "List at" price calculation by removing the dangerous fallback and improve source quality by tightening the Keepa Query.

## Steps

### 1. Remove the "High Velocity" Fallback
**File:** `keepa_deals/stable_calculations.py`
**Function:** `analyze_sales_performance`

Locate and remove the following block of code:
```python
    # --- High-Velocity / Sparse Data Fallback ---
    # If we have insufficient inferred sales (e.g. graph too smooth for drops), try using monthlySold + Avg Price
    peak_price_mode_cents = -1

    if not peak_season_prices:
        monthly_sold = product.get('monthlySold', -1)
        # ... [Logic checking monthly_sold > 20 and using avg90] ...
             if avg90 and len(avg90) > 2 and avg90[2] > 0:
                 peak_price_mode_cents = avg90[2]
                 # ...
```
**Correct Behavior:** If `peak_season_prices` is empty (meaning no inferred sales were found), `peak_price_mode_cents` should remain `-1`. The function should return `-1`, leading to the deal being excluded. Do not attempt to guess the price.

### 2. Tighten Keepa Query
**File:** `keepa_query.json`

Update the `salesRankRange` to exclude low-velocity items that are prone to "Zombie" behavior.

**Change:**
```json
"salesRankRange": [
    100000,
    5000000
]
```
**To:**
```json
"salesRankRange": [
    50000,
    1000000
]
```
(Adjust the lower bound as needed, but the upper bound should be capped at 1,000,000).

### 3. Verify Fix (Simulation)
Create a simulation script (similar to the investigation) that feeds a mock "Zombie Product" (High monthlySold, High Used Price, Low New Price) into `analyze_sales_performance`.
-   **Before Fix:** It should return the High Used Price (e.g., $400).
-   **After Fix:** It should return `-1` (Invalid/Missing List at).

### 4. Verify System Flow
Run the system (or wait for the Backfiller) and verify that:
1.  The Rejection Rate drops (because we aren't even trying to process the "Zombie" items that were previously getting rejected by AI).
2.  Accepted deals have valid, reasonable prices.
