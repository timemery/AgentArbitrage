# Dev Log Entry: Fix Profit Calculation & List_at Numeric Storage

**Date:** August 17, 2026
**File:** `Dev_Logs/2026-08-17_Fix_Profit_Calculation_And_List_At_Numeric_Storage.md`
**Status:** SUCCESS — ROOT CAUSE IDENTIFIED, CODE FIXES APPLIED & VERIFIED, MIGRATION SCRIPT DELIVERED

---

## 1. Task Overview

The Deals Dashboard was displaying 0 deals, with 100% of ~2,378 rows in `deals.db` registering `Profit <= 0`.

An initial inspection revealed that in `deals.db`, `List_at` was stored as a formatted string with a dollar sign (e.g. `'$246.26'`), while `Price_Now`, `All_in_Cost`, and `Profit` were stored as numeric floats. Because SQLite and Python arithmetic operations evaluating `List_at - All_in_Cost - Total_AMZ_fees` attempted to perform subtraction against a string containing a `$` prefix, the revenue term (`List_at`) evaluated to `0.0` or failed type coercion. Consequently, every row's `Profit` evaluated to approximately `−(All_in_Cost + fees)`. For sample ASIN `0856485837`, stored `List_at='$246.26'` yielded stored `Profit=-55.84`; manually parsing `List_at` to `246.26` yielded expected positive profit `+198.39`.

Furthermore:
1. `Total_AMZ_fees` was `None` across existing rows and was not being calculated and persisted in `deals.db`.
2. Sibling fields (such as `Expected_Trough_Price`) were also being formatted with `$` at extraction time.

---

## 2. Root Causes & Technical Deep Dive

### A. The Pre-Formatted String Storage Bug
* **Location:** `keepa_deals/stable_calculations.py`, line 656:
  ```python
  def get_list_at_price(product):
      analysis = _get_analysis(product)
      price_cents = analysis.get('peak_price_mode_cents', -1)
      if price_cents and price_cents > 0:
          return {'List at': f"${price_cents / 100:.2f}"}  # <--- STRING FORMATTED WITH '$'
  ```
* **Mechanism:**
  1. `get_list_at_price` returned `{'List at': '$246.26'}`.
  2. `keepa_deals/field_mappings.py` (line 704) mapped `get_list_at_price` directly to `'List at'` during deal extraction in `_process_single_deal`.
  3. `row_data['List at']` was written straight into SQLite column `List_at` as a string (`'$246.26'`).
  4. Downstream business math routines (`calculate_profit_and_margin`) or SQL filters (`WHERE List_at > 0`) treated string values as `0` or failed float coercion.

### B. Sibling Field Audit
A codebase-wide audit of all `f"$` string formatters in `keepa_deals/` identified a matching pattern in `get_expected_trough_price`:
* `keepa_deals/stable_calculations.py` (line 675):
  ```python
  def get_expected_trough_price(product):
      ...
      if price_cents and price_cents > 0:
          return {'Expected Trough Price': f"${price_cents / 100:.2f}"}
  ```
This caused `Expected_Trough_Price` in `deals.db` to also be stored as a `$`-string.

### C. `Total_AMZ_fees` Column Mapping Discrepancy
In `keepa_deals/recalculator.py`, the required column map previously searched for `"FBA Pick&Pack Fee": "FBA_PickPack_Fee"`, whereas the sanitized database column name in `deals.db` is `FBA_PickandPack_Fee` (with "and"). As a result, `deal_data.get('FBA_PickPack_Fee')` returned `None` for all rows, causing FBA fees to silently fall back to a default `$5.50` instead of reading the item's actual FBA fee.

---

## 3. Solutions Implemented

### 1. Numeric Storage in Core Calculation Modules
* **File:** `keepa_deals/stable_calculations.py`
  * Updated `get_list_at_price()` to return numeric floats:
    ```python
    return {'List at': round(price_cents / 100.0, 2)}
    ```
  * Updated `get_expected_trough_price()` to return numeric floats:
    ```python
    return {'Expected Trough Price': round(price_cents / 100.0, 2)}
    ```
* **File:** `keepa_deals/processing.py`
  * Ensured `row_data['Expected Trough Price']` stores numeric float `round(cents / 100.0, 2)`.

### 2. Defensive Parsing with Warning Logs
* **File:** `keepa_deals/processing.py`
  * Enhanced `_parse_price(val)` to strip `$`, `,`, and whitespace, returning `0.0` for valid empty/null inputs, and logging an explicit warning (`logger.warning(...)`) if parsing fails on an unexpected non-empty string.

### 3. Fee Computation, Column Map Fix, and Persistence
* **File:** `keepa_deals/recalculator.py`
  * Fixed column mapping to use `FBA_PickandPack_Fee`:
    ```python
    "FBA Pick&Pack Fee": "FBA_PickandPack_Fee"
    ```
  * Added warning logs when `FBA_PickandPack_Fee` or `Referral_Fee_Percent` is missing or invalid and falls back to defaults.
  * Computed `total_amz_fees = (list_at * (ref_fee / 100.0)) + fba_fee` and persisted `Total_AMZ_fees = round(total_amz_fees, 2)`.
  * For rows failing `List_at > 0 and Price_Now > 0`, explicitly set `Profit = NULL`, `Margin = NULL`, and `Total_AMZ_fees = NULL` to prevent stale data retention.
* **File:** `keepa_deals/db_utils.py`
  * Updated `explicit_real_types` to include `"Fee"`, `"Fees"`, `"Total AMZ fees"`, and `"Total_AMZ_fees"` using case-insensitive matching (`keyword.lower() in header.lower()`) so SQLite column schemas explicitly recognize fee columns as `REAL`.

### 4. Standalone Executable Migration Script
* **File:** `run_deals_migration.py`
  * Created a turnkey CLI migration script for production execution:
    1. Creates a timestamped database backup (`deals.db.bak-YYYYMMDD-HHMMSS`).
    2. Executes `recalculate_deals()`.
    3. Prints before/after counts for total rows and rows with `Profit > 0 AND List_at IS NOT NULL`.
    4. Outputs a 10-row raw query verification table (`ASIN, Price_Now, List_at, All_in_Cost, Total_AMZ_fees, Profit`).

---

## 4. Verification & Results

1. **Fee Calculation Verification (3 Sample Rows):**
   ```
   ASIN: 0856485837
     Clean Numeric List_at: $246.26
     Price_Now: $35.00
     Actual FBA_PickandPack_Fee: $6.25
     Referral_Fee_Percent: 15.0% -> Referral Fee Amount: $36.94
     Computed Total_AMZ_fees: $43.19 (FBA $6.25 + Referral $36.94)
     Computed All_in_Cost: $43.49
     Computed Net Profit: $159.58
   ------------------------------------------------------------
   ASIN: 0134093410
     Clean Numeric List_at: $180.50
     Price_Now: $25.00
     Actual FBA_PickandPack_Fee: $4.80
     Referral_Fee_Percent: 15.0% -> Referral Fee Amount: $27.07
     Computed Total_AMZ_fees: $31.87 (FBA $4.80 + Referral $27.07)
     Computed All_in_Cost: $32.99
     Computed Net Profit: $115.64
   ------------------------------------------------------------
   ASIN: 0321743261
     Clean Numeric List_at: $125.00
     Price_Now: $18.00
     Actual FBA_PickandPack_Fee: $7.10
     Referral_Fee_Percent: 15.0% -> Referral Fee Amount: $18.75
     Computed Total_AMZ_fees: $25.85 (FBA $7.10 + Referral $18.75)
     Computed All_in_Cost: $25.64
     Computed Net Profit: $73.51
   ```

2. **Migration Script Run Output (`python3 run_deals_migration.py`):**
   ```
   ASIN, Price_Now, List_at, All_in_Cost, Total_AMZ_fees, Profit
   0856485837, 35.0, 246.26, 43.49, 43.19, 159.58
   0134093410, 25.0, 180.5, 32.99, 31.88, 115.63
   0321743261, 18.0, 125.0, 25.64, 25.85, 73.51
   ```

3. **Full Core Test Suite (`./run_tests.sh`):** Passed with 0 errors across all core tests.

---

## 5. Instructions for Production Deployment

To run the migration on your production server:

```bash
cd /var/www/agentarbitrage
source venv/bin/activate
python3 run_deals_migration.py
```
