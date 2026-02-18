# Dev Log: Fix Ghost Deals (Unknown Shipping Vulnerability)

**Date:** 2026-02-03
**Task:** Prevent "Ghost Deals" where international MFN sellers appear with artificially low prices.
**Status:** Successful

## Overview
A critical issue was identified where "Ghost Deals" appeared on the dashboard. These deals showed a very low price (e.g., $19.98) but when the user clicked through to Amazon, the cheapest offer was significantly higher (e.g., $41.24). This was traced to international MFN (Merchant Fulfilled) sellers whose shipping costs were unknown to Keepa.

## Root Cause Analysis
The function `get_used_product_info` in `keepa_deals/seller_info.py` parses the `offerCSV` from Keepa. The CSV format is `[time, price, shipping, ...]`.
Keepa uses `-1` to indicate "Unknown Shipping".

**The Flaw:**
The original logic was:
```python
shipping_cost = offer_csv[-1] if offer_csv[-1] != -1 else 0
```
This blindly assumed that if shipping is unknown, it is Free ($0).
*   **For FBA (Prime):** This is generally correct/safe.
*   **For MFN (Merchant):** This is **dangerous**, especially for international sellers (e.g., UK seller "Bahamut Media" on .com). The shipping is not $0; it's just unknown via the API (or hidden/high).

This caused the system to calculate `Total Price = Item Price + 0`, resulting in a "Ghost Deal" that looked profitable but didn't exist in reality.

## Solution
We modified the logic to enforce strict checks on MFN shipping:

1.  **Check Fulfillment Type:** We retrieve `isFBA` status.
2.  **Conditional Default:**
    *   **If FBA and Shipping is -1:** Default to `0` (Safe/Standard Prime behavior).
    *   **If MFN and Shipping is -1:** **REJECT THE OFFER**. We skip this offer entirely. We cannot safely arbitrate a deal with unknown shipping costs.

This ensures that only verifiable prices make it to the dashboard.

## Verification
*   **Unit Test:** Created `tests/test_shipping_logic.py`.
    *   `test_mfn_unknown_shipping_unsafe`: Confirmed that an MFN offer with `-1` shipping is now rejected (returns `None`).
    *   `test_fba_unknown_shipping_safe`: Confirmed that an FBA offer with `-1` shipping is still accepted with $0 shipping.

## Files Changed
*   `keepa_deals/seller_info.py`
*   `tests/test_shipping_logic.py`
