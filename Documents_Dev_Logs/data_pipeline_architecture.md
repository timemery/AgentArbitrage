# Data Pipeline Architecture

This document specifies the underlying implementation and logic for the data acquisition pipeline, specifically the `backfill_deals` Celery task. Its purpose is to serve as the definitive technical blueprint to prevent regressions and ensure the process remains efficient and correct.

## Core Principle: Efficiency and Data Freshness

The primary goal is to acquire all necessary data to populate a single deal row in the database with the minimum number of API calls and tokens. The process must prioritize using the most current, "live" offer data to find the lowest price, rather than relying on potentially stale summary statistics.

## Step-by-Step Data Acquisition Logic

The `backfill_deals` task processes deals in small, sequential chunks (e.g., of size 2) to ensure a steady flow of data into the database. For each chunk of ASINs, the following steps must be executed:

### Step 1: Fetch Live Product and Offer Data

*   **Action:** Make a single, batched `/product` API call for the ASINs in the chunk.
*   **Parameters:** This call MUST include the `offers=20` (or a similar low number) parameter. This is critical as it retrieves the live, currently available offers for each product.
*   **Result:** A product data object for each ASIN, which contains a list under the `offers` key.

### Step 2: Identify the Single Lowest-Priced "Used" Offer

*   **Action:** For each product, iterate through the list of live offers returned in the `offers` array from Step 1.
*   **Logic:**
    *   Filter for offers where the condition is "Used" (e.g., 'Used - Good', 'Used - Very Good', etc.).
    *   Calculate the total price for each offer (`price` + `shippingCost`).
    *   Identify the offer with the absolute minimum total price.
*   **Result:** The specific offer object and, most importantly, the `sellerId` of the one seller who is currently offering the lowest used price.

### Step 3: Fetch Data for the Target Seller ONLY

*   **Action:** Make a single, targeted `/seller` API call.
*   **Parameters:** This call uses the `sellerId` identified in Step 2.
*   **Result:** The detailed seller information (e.g., seller name, rating, etc.) for *only* the seller with the lowest-priced offer.

### Step 4: Process and Save the Deal

*   **Action:** Consolidate the data from the previous steps:
    1.  The overall product data (from Step 1).
    2.  The specific lowest-priced offer data (from Step 2).
    3.  The target seller's data (from Step 3).
*   **Logic:** Pass this consolidated data to the processing functions to perform all necessary calculations.
*   **Result:** A complete deal row is saved to the database.

This architecture ensures that for each deal, we only make one `/product` call and one `/seller` call, consuming the absolute minimum number of API tokens required to get fresh, accurate data.
