# Architectural Patterns for a Scalable Keepa Deals Pipeline

## 1. The Problem: Scalability and Data Freshness

The current data pipeline operates on a "full backfill, then incremental update" model. While effective for small datasets, this approach does not scale. A full backfill of 15,000+ deals could take over a week, at which point the initial data is already stale. The goal is to evolve the architecture to support a large, continuously growing, and consistently up-to-date database without a massive upfront time investment.

Below are three conceptual models to achieve this.

---

## Option 1: The "Scout/Processor/Refresher" Model (Decoupled Workers)

This is the most robust and scalable approach, mirroring a microservices architecture. It breaks the monolithic task into three independent, specialized workers.

*   **Concept:** The pipeline is split into three distinct jobs: finding new deals, performing heavy processing on them, and periodically refreshing old ones. These jobs run independently and continuously, creating a self-maintaining system.

*   **Components:**
    1.  **The "Scout" Worker:**
        *   **Job:** Discovers new potential deals.
        *   **Action:** Runs frequently (e.g., every 5-10 minutes). It makes a cheap API call to the Keepa `/deal` endpoint to get a list of new ASINs. For each ASIN, it checks if it already exists in the database. If not, it inserts the ASIN with a status of `'pending_processing'`.
    2.  **The "Processor" Worker:**
        *   **Job:** Enriches deals with full data.
        *   **Action:** Runs continuously as a queue processor. It queries the database for a small batch of deals with the `'pending_processing'` status. For each deal, it performs all the expensive, time-consuming API calls (full product data, seller info, XAI analysis). After processing, it updates the deal's database row with all the new data and changes its status to `'active'`.
    3.  **The "Refresher" Worker:**
        *   **Job:** Ensures data doesn't become stale.
        *   **Action:** Runs periodically (e.g., once or twice a day). It queries the database for `'active'` deals that haven't been updated in a set period (e.g., 7 days). It simply changes their status back to `'pending_processing'`, which automatically puts them back into the Processor's queue for a complete refresh.

*   **Pros:**
    *   **Extremely Scalable:** The Processor can be scaled to multiple workers to increase throughput.
    *   **No "Dead Time":** The database grows organically, and new data becomes available as soon as it's processed, rather than after a week-long wait.
    *   **Robust & Resilient:** If one part of the system fails (e.g., the XAI service is down), it only affects the Processor, while the Scout can continue discovering new deals.
    *   **Efficient:** Uses the cheapest API calls for discovery and saves the expensive calls for targeted processing.

*   **Cons:**
    *   **Highest Complexity:** Requires implementing and managing three separate Celery tasks and a more complex database schema (e.g., adding `status` and `last_updated` columns).

---

## Option 2: The "Priority Queue" Model (Tiered Refresh Strategy)

This model focuses on using the API budget as efficiently as possible by ensuring the "hottest" or newest deals are updated more frequently than older ones.

*   **Concept:** Instead of a simple "active" or "pending" status, deals are assigned a priority level. The system always works on the highest-priority tasks first, which includes fetching new deals and refreshing recent ones.

*   **Components:**
    *   **A Single, Smart Worker:** A continuous Celery task that orchestrates the entire process.
    *   **Priority System:** The database schema is modified to include a `priority` (e.g., an integer from 1-5) and a `next_update_due` timestamp.
    *   **Workflow:**
        1.  The worker always starts by checking the Keepa `/deal` endpoint for new ASINs. Any new discoveries are inserted with the highest priority (e.g., `priority = 1`) and a `next_update_due` of right now.
        2.  Next, the worker queries its own database for the single highest-priority deal where `next_update_due` is in the past.
        3.  It fully processes this one deal.
        4.  After processing, it **de-prioritizes** the deal. For example, a `priority 1` deal becomes `priority 2` and its `next_update_due` is set to 24 hours in the future. A `priority 2` might become `priority 3` with its next update due in 3 days, and so on.

*   **Pros:**
    *   **Focus on Freshness:** Guarantees that the newest and most relevant deals are always the most up-to-date.
    *   **Simpler Architecture:** Involves only one primary worker task, reducing orchestration complexity.
    *   **Efficient API Use:** Spends the majority of the API budget on data that changes most often.

*   **Cons:**
    *   **Stale Tail-End:** Older, lower-priority deals may become very stale if the influx of new, high-priority deals is constant.
    *   **Complex Logic:** The priority and scheduling logic within the single worker can become quite complex to manage and debug.

---

## Option 3: The "Hybrid Backfill & Live" Model (Phased Approach)

This approach is an evolution of the current system, attempting to add a live component without a full architectural rewrite.

*   **Concept:** A very slow, continuous backfill runs in the background to build the large historical dataset. In parallel, a fast, separate task keeps a small, "live" subset of the most recent deals perfectly up-to-date.

*   **Components:**
    1.  **The "Trickle" Backfiller:**
        *   **Job:** Slowly builds the main database.
        *   **Action:** This Celery task runs on a simple schedule (e.g., every hour). During each run, it processes just *one page* of deals from the main Keepa query, then stops. It saves its current page number so it knows where to resume on the next run. This allows it to slowly build the 15,000-deal database over many days without ever consuming the entire API budget.
    2.  **The "Live" Upserter:**
        *   **Job:** Keeps the very latest deals fresh.
        *   **Action:** This is nearly identical to the current `update_recent_deals` task. It runs every 15 minutes, uses the `/deal` endpoint, and only fetches/updates deals that have changed since its last run.

*   **Pros:**
    *   **Easiest to Implement:** Requires the least amount of refactoring from the current state.
    *   **Immediate Value:** Users get access to live, up-to-the-minute deals right away, even while the main database is still being built.

*   **Cons:**
    *   **Data Dichotomy:** Creates two classes of data: the small, fresh set and the large, mostly stale set. The bulk of the database is only as fresh as the last time the "Trickle" backfiller happened to hit that page, which could be weeks ago.
    *   **Doesn't Solve the Core Problem:** This is more of a workaround than a solution. It doesn't provide an efficient mechanism for keeping the *entire* 15,000-deal database up-to-date.

---

### Recommendation

For building a truly scalable and self-maintaining system that can handle 15,000+ deals while ensuring data integrity and freshness, **Option 1 (The "Scout/Processor/Refresher" Model)** is the superior architectural choice. While it requires more initial development effort, it provides a robust, resilient, and highly scalable foundation that will meet your long-term goals far more effectively than the other options.