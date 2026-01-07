### **Next Steps: A New Plan Based on Keepa's Advice**

Here is the new 4-part plan that combines the original project goals with the excellent, specific advice from the Keepa support team. This provides a clear, efficient, and achievable roadmap.

**New 4-Part Plan: The Keepa Incremental Sync Strategy**

**Core Concepts:**

- **Watermark:** A timestamp (`lastUpdate` from a Keepa deal) that represents the "newest" deal currently stored in our local database. This is the key to finding the "delta" on each subsequent run.
- **Backfiller Task:** A one-time, heavy-lifting task responsible for the initial, full population of the database.
- **Upserter Task:** A lightweight, frequently-run task responsible for fetching only the new or changed deals since the last run.

------

**Part 1: Create the Watermark Manager & The "Backfiller" Task**

- **Objective:** To perform the initial, one-time population of the `deals.db` database with all historical deals matching the user's criteria.
- Key Steps:
  1. **Create a Watermark Manager:** Implement a simple utility (e.g., in `db_utils.py`) to save and load a timestamp value from a persistent file (e.g., `watermark.json`). This will store the `lastUpdate` timestamp of the newest deal found.
  2. **Create a `backfill_deals` Task:** Create a new, dedicated Celery task.
  3. This task will call the `/deal` endpoint with the hardcoded query filters.
  4. It will paginate through *all* available results until the API returns no more deals.
  5. For each batch of ASINs, it will call the `/product` endpoint to get full details.
  6. It will process and save all of this data to the `deals.db`.
  7. Crucially, after processing all deals, it will identify the most recent `lastUpdate` timestamp among all the deals it found and save this value using the Watermark Manager.

------

**Part 2: Refactor the "Upserter" Task for Incremental Sync**

- **Objective:** To modify the existing `update_recent_deals` task to perform an efficient incremental (delta) sync.
- Key Steps:
  1. The task will begin by loading the current watermark timestamp using the Watermark Manager.
  2. It will call the `/deal` endpoint with the same filters, ensuring the sort order is `newest first`.
  3. It will process the first page of results. A new "newest" timestamp should be tracked from the deals in the response.
  4. It will **stop paginating** as soon as it finds a deal whose `lastUpdate` timestamp is less than or equal to the watermark loaded in step 1.
  5. It will then fetch full product details for only the new ASINs (the "delta").
  6. After saving the new deals to the database, it will save the new "newest" timestamp as the new watermark.

------

**Part 3: Create a UI for Triggering and Monitoring**

- **Objective:** To provide a way for the user to initiate and monitor the Backfiller and Upserter tasks.
- Key Steps:
  1. Add a "Run Full Backfill" button to one of the admin pages (e.g., `settings.html`) that triggers the `backfill_deals` task. This should have a strong warning that it is a long-running, token-heavy process.
  2. Add a "Run Incremental Sync" button that triggers the `update_recent_deals` task.
  3. Display the current watermark timestamp on the page so the user can see how up-to-date the system is.

------

**Part 4: Refactor the `recalculate_deals` Task**

- **Objective:** To ensure the existing `recalculate_deals` task is purely a database operation and makes no API calls, solidifying the separation of concerns.
- Key Steps:
  1. Review the code for the `recalculate_deals` task.
  2. Ensure it reads all data *from the local `deals.db` only*.
  3. Ensure it re-applies the latest business logic and settings and `UPDATE`s the rows in the database.
  4. Confirm that it makes **zero** Keepa API calls, thus consuming zero tokens.

------

**Keepa Docs you can skim for parameters/examples:**

- Browsing Deals
  - https://keepa.com/#!discuss/t/browsing-deals/338
- Products
  - https://keepa.com/#!discuss/t/products/110
- Deal Object
  - https://keepa.com/#!discuss/t/deal-object/412
- Product Object
  - https://keepa.com/#!discuss/t/product-object/116

