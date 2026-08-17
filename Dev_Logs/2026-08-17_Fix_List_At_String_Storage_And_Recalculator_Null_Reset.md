# Dev Log Entry: Fix List_at String-Type Storage & Recalculator NULL-Reset Filter

**Date:** August 17, 2026  
**File:** `Dev_Logs/2026-08-17_Fix_List_At_String_Storage_And_Recalculator_Null_Reset.md`  
**Status:** SUCCESS — BUGS IDENTIFIED, CODE FIXES APPLIED & VERIFIED  

---

## 1. Task Overview

This task addressed two independent bugs in the deals pipeline verified via live production queries:

1. **Bug 1: `List_at` stored as `$`-prefixed TEXT instead of float**  
   - **Symptom:** Live query on recently ingested rows showed `typeof(List_at)` = `text` with a `$` prefix (e.g., `'$109.44'`).
   - **Requirement:** Ensure `List_at`, `Expected_Trough_Price`, and `Total_AMZ_fees` are written as numeric floats (`typeof` = `real`) on both the ingestion path (`_process_single_deal` / `processing.py`) and the recalculator path (`recalculate_deals` / `recalculator.py`). `$` formatting must occur exclusively at display/API time.

2. **Bug 2: Recalculator write loop strips explicit NULLs**  
   - **Symptom:** In `recalculator.py`, when a deal failed validation (`List_at > 0 and now_price > 0`), the `else` branch correctly assigned `{'Profit': None, 'Margin': None, 'Total_AMZ_fees': None}`. However, the write loop filtered out `None` values:
     ```python
     update_dict = {k: v for k, v in row.items() if v is not None and k != 'ASIN'}
     ```
     This caused all-None updates to be skipped, leaving stale profit figures in `deals.db` rather than setting them to SQL `NULL`.
   - **Requirement:** Modify the write loop to explicitly whitelist `Profit`, `Margin`, and `Total_AMZ_fees` so `None` values write as SQL `NULL`, while preserving the `None` filtering for all other columns and excluding `ASIN` from the `SET` clause.

---

## 2. Root Cause Analysis & Ingestion Trace

### A. Ingestion Path & Float Conversion
- **Getter Verification (`keepa_deals/stable_calculations.py`, line 656):**
  `get_list_at_price(product)` was previously fixed to return a numeric float:
  ```python
  return {'List at': round(price_cents / 100.0, 2)}
  ```
- **Numeric Cleaning (`keepa_deals/processing.py`, line 297):**
  `clean_numeric_values` cleans numeric keys in row dictionaries. Previously, its type-coercion check checked keys matching `["Price", "Cost", "Fee", "Profit", "Margin", "Avg"]`. Because `"List"` was not included, if `List at` ever arrived as a string or string representation, it bypassed float coercion. Adding `"List"` and `"Fees"` ensures string inputs like `"$109.44"` are cleaned to float `109.44`.
- **Database Column Mapping (`keepa_deals/db_utils.py`):**
  In `db_utils.py`, `explicit_real_types` includes `"List at"`, `"Total AMZ fees"`, `"Total_AMZ_fees"`, `"Profit"`, `"Margin"`, and `"Price"`. When numeric floats are passed into `save_deals_to_db` or `recalculate_deals`, SQLite stores them as `REAL`.
- **Finding regarding existing DB rows vs new writes:**
  Newly ingested rows processed by `_process_single_deal` -> `clean_numeric_values` -> `save_deals_to_db` already write as clean floats (`typeof` = `real`). Rows exhibiting `typeof` = `text` were legacy historical rows that had not been backfilled/recalculated.

### B. Recalculator Write Loop
- In `keepa_deals/recalculator.py`:
  When a deal had `List_at <= 0` or `Price_Now <= 0`, `row_updates` was assigned:
  ```python
  row_updates.update({'Profit': None, 'Margin': None, 'Total_AMZ_fees': None})
  ```
  However, the subsequent update dict comprehension:
  ```python
  update_dict = {k: v for k, v in row.items() if v is not None and k != 'ASIN'}
  ```
  completely stripped `'Profit'`, `'Margin'`, and `'Total_AMZ_fees'` because their values were `None`. Thus `update_dict` became empty, no `UPDATE` query was executed, and stale numbers remained in the database.

---

## 3. Solutions Implemented

### 1. Ingestion Path Clean Numeric Coercion (`keepa_deals/processing.py`)
Updated `clean_numeric_values` to include `"List"` and `"Fees"`:
```python
<<<<<<< SEARCH
        elif any(k in key for k in ["Price", "Cost", "Fee", "Profit", "Margin", "Avg"]):
            try: row_data[key] = float(cleaned_value)
            except (ValueError, TypeError): row_data[key] = None
=======
        elif any(k in key for k in ["Price", "Cost", "Fee", "Fees", "Profit", "Margin", "Avg", "List"]):
            try: row_data[key] = float(cleaned_value)
            except (ValueError, TypeError): row_data[key] = None
>>>>>>> REPLACE
```

### 2. Recalculator Write Loop NULL Whitelist (`keepa_deals/recalculator.py`)
Updated `recalculate_deals` write loop to whitelist `Profit`, `Margin`, and `Total_AMZ_fees` as NULL-allowed:
```python
<<<<<<< SEARCH
        update_count = 0
        for row in all_rows_to_update:
            try:
                update_dict = {k: v for k, v in row.items() if v is not None and k != 'ASIN'}
                if not update_dict: continue
=======
        update_count = 0
        NULL_ALLOWED_COLS = {'Profit', 'Margin', 'Total_AMZ_fees'}
        for row in all_rows_to_update:
            try:
                update_dict = {
                    k: v for k, v in row.items()
                    if (v is not None or k in NULL_ALLOWED_COLS) and k != 'ASIN'
                }
                if not update_dict: continue
>>>>>>> REPLACE
```

---

## 4. Verification & Results

1. **Numeric Storage Verification (`typeof` check on fresh ingestion):**
   - Ingested test row `0521246768`:
     ```
     ASIN: 0521246768
     List_at: 109.44 | typeof(List_at): real
     Total_AMZ_fees: 22.26 | typeof(Total_AMZ_fees): real
     ```

2. **Recalculator NULL Reset Verification:**
   - Evaluated valid deal vs invalid deal (`List_at = 0.0`, `Price_Now = 0.0`) through `recalculate_deals()`:
     - **Before Recalculation:**
       - `VALID_01`: Profit = 30.0
       - `INVALID_02`: Profit = 15.0 (stale) | NULL Profit count = 0
     - **After Recalculation:**
       - `VALID_01`: Profit = 20.26 (`typeof` = `real`), Total_AMZ_fees = 20.5 (`typeof` = `real`)
       - `INVALID_02`: Profit = `None` (`typeof` = `null`), Margin = `None` (`typeof` = `null`), Total_AMZ_fees = `None` (`typeof` = `null`)
       - NULL Profit count = 1

3. **Unit Tests:**
   - Ran `PYTHONPATH=. python3 -m unittest tests/test_processing_integrity.py` — 3/3 tests passed with 0 errors.

---

## 5. Summary of Files Modified

- `keepa_deals/processing.py`: Added `"List"` and `"Fees"` to `clean_numeric_values` float coercion.
- `keepa_deals/recalculator.py`: Updated write loop to allow explicit `None` values for `Profit`, `Margin`, and `Total_AMZ_fees` to be written as SQL `NULL`.
