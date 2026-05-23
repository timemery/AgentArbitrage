# Dev Log: Diagnose Sales & Profit Tab Missing Columns

**Date:** 2026-05-23
**Author:** Jules (AI Agent)
**Status:** Investigation Complete

## 1. Task Overview
The objective was to investigate two issues on the Tracking page -> Sales & Profit tab:
1. The Fees column displays $0.00 for every row.
2. The Profit ($) and ROI (%) columns are missing.

This was an investigation-only task with no code changes authorized.

## 2. Investigation Findings

### The $0.00 Fees Issue
* **Root Cause:** The SP-API Orders v0 endpoint (`/orders/v0/orders/{order_id}/orderItems`) used in `keepa_deals/sp_api_tasks.py` to ingest sales data does not return fee information, resulting in a hardcoded `0` being inserted into the `sales_ledger` database table and `$0.00` being displayed on the frontend.
* **API Details:** The `fetch_order_items` function in `keepa_deals/amazon_sp_api.py` correctly queries the Orders API, but Amazon separates fee data into the Finances API. Retrieving exact fees per order would require building a new integration with the Finances API.

### Missing Profit and ROI Columns
* **Data Availability:** The raw components needed to calculate Profit and ROI exist in the database, but they are split across two tables that are not currently joined in the API response.
* **Ledger Disconnect:** The `/api/tracking/sales` endpoint in `wsgi_handler.py` currently only queries the `sales_ledger` (which holds the realized `sale_price`). It does not `JOIN` the `inventory_ledger` (which holds the `buy_cost`).
* **Calculation Logic:** The application already possesses robust profit calculation logic in `keepa_deals/business_calculations.py` (`calculate_all_in_cost` and `calculate_profit_and_margin`).

## 3. Analysis of Profit Calculation Reusability
The user requested an analysis of how the Dashboard calculates profit and whether it can be reused for the Sales & Profit tab.

* **Reusability:** The Dashboard's `calculate_profit_and_margin` function can and should be reused. To calculate realized profit for a past sale, the system should:
  1. Retrieve the realized `sale_price` from `sales_ledger`.
  2. Retrieve the original `buy_cost` from `inventory_ledger` (via `reconciliation_log` FIFO matching).
  3. Estimate the Amazon Fees (referral fee + FBA fee) based on the ASIN's current profile.
  4. Call `calculate_profit_and_margin(realized_sale_price, buy_cost, estimated_fees)`.
* **Historical Settings:** The `calculate_all_in_cost` function reads point-in-time global settings from `settings.json` (Prep Fee, Tax, etc.). The system does not snapshot these settings at the time of purchase. However, since the `inventory_ledger` stores the final calculated `buy_cost` at the moment the inventory is logged, historical cost settings are effectively "baked in" and preserved. The Amazon Fees, however, will be estimated based on current FBA fee structures unless exact past fees are fetched via the Finances API. This is acceptable for a "Realized Profit (Estimated)" view.
* **Shipping Direction:** The $3.99 "Estimated Shipping Per Book" setting in `settings.json` correctly represents *inbound* shipping (seller to Amazon warehouse), which is a legitimate out-of-pocket cost. The Dashboard's `calculate_all_in_cost` function correctly treats this as an acquisition cost. It does not incorrectly subtract outbound shipping (which Amazon pays for FBA).

## 4. Recommended Path Forward

* **For Fees:** Remove the Fees column entirely. Since exact fees require a complex new Finances API integration, and we can reliably estimate Realized Profit using the existing Dashboard calculation logic, the Fees column is redundant and misleading.
* **For Profit & ROI:** 
  1. Update the `get_sales_history()` SQL query in `wsgi_handler.py` to `LEFT JOIN` the `reconciliation_log` and `inventory_ledger`. This will match the realized `sale_price` with the specific unit's `buy_cost` using the existing FIFO logic.
  2. Implement backend logic in `get_sales_history()` to fetch the ASIN's estimated FBA and Referral fees (likely by querying the `deals` table or a cached API response).
  3. Calculate the realized profit and ROI on the backend using the retrieved `buy_cost`, `sale_price`, and estimated fees.
  4. Update `tracking.html` to display these new columns.
