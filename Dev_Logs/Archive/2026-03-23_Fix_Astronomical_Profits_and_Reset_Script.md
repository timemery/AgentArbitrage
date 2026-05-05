# Fix Astronomical Profits & Add Non-Interactive Database Reset Script

**Date:** 2026-03-23
**Author:** Agent Jules
**Status:** Success (Backend Verified)

## Overview
The primary goal of this task was to resolve an issue where the Deals Dashboard was displaying highly unrealistic, astronomical profit estimates (e.g., $3,000+) derived from absurdly high "List At" prices (e.g., $4,000 for a used book). The user also requested a command-line script to safely clear old, inaccurate deals data without wiping out credentials or interrupting deployed code.

## Challenges
1.  **Bypassed/Lenient AI Reasonableness Checks:**
    - The existing `is_suspiciously_high` logic in `keepa_deals/stable_calculations.py` (which forces an AI Reasonableness Check if the price ratio > 3x the current used price) was strictly limited to "Keepa Stats Fallback" or "Inferred Sales (Sparse)" data. This meant that mathematically skewed "Inferred Sales" could still slip through without intense scrutiny.
    - Even when the AI *was* queried, the prompt instructed it that peak prices could "validly be 200-400% higher than the average" for seasonal items, causing the AI to occasionally green-light absolutely absurd prices like $4,000 if it lacked sufficient contrasting metadata.
    - There was no absolute mathematical limit on how high a `List At` price could be calculated.
2.  **Lack of Deployment-Friendly Cleanup Tools:**
    - The existing `Diagnostics/reset_database.py` script required an interactive "YES" prompt, preventing the user from chaining it cleanly with deployment scripts like `./deploy_update.sh`.

## Solutions Implemented

### 1. Robust Reasonableness & Safety Boundaries
*   **Absolute Hard Ceiling:** Introduced a strict `is_absurdly_high` check in `keepa_deals/stable_calculations.py` that automatically rejects *any* calculated `peak_price_mode_cents` exceeding $1,500 without ever querying the AI. This prevents extreme outliers from polluting the dashboard regardless of their source.
*   **Universal Suspicious Ratio Check:** Modified the `is_suspiciously_high` logic so the `> 3.0` ratio check (calculated List Price vs. Current Used Price) now applies to **all** price sources, ensuring any disproportionately large markup is subjected to AI validation.
*   **Stricter AI Scrutiny Prompt:** Updated the prompt used in `_query_xai_for_reasonableness` to explicitly instruct the model that "any used book price over $500 should face intense scrutiny... and prices over $1,000 are almost always unreasonable."

### 2. Database Cleanup Scripts
*   **Modified `Diagnostics/reset_database.py`:** Added an optional `--force` argument to bypass the interactive user confirmation prompt.
*   **Created `clear_deals.sh`:** Placed a convenience bash script in the repository root that executes `python3 Diagnostics/reset_database.py --force`. This provides the user with a single, safe command to drop and recreate the `deals` and `user_restrictions` tables prior to deployment without risking user credentials or the inventory tracking ledger.

## Outcome
The task was completely successful. Astronomical list prices and their associated "fake profits" are now successfully clamped and rejected by mathematical bounds and improved AI reasoning. The user can safely wipe out lingering bad data using `./clear_deals.sh` directly before updating deployments.
