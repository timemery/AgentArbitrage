# Architectural Blueprint: A Scalable Keepa Deals Pipeline

## 1. The Goal: Scalability and Real-Time Data Freshness

The current data pipeline, while functional for small datasets, does not scale to support a large, continuously updated database of tens of thousands of deals. The "full backfill, then incremental update" model results in a long initial data-load time (potentially weeks), rendering the data stale by the time it's fully available.

This document outlines the chosen architectural pattern to solve this problem. The goal is to build a system that supports a large, continuously growing database while ensuring the data presented to the user is always fresh and up-to-date, even during the initial large-scale backfill.

---

## 2. The Chosen Architecture: The "Scout/Processor/Refresher" Model

This is a robust and scalable approach that mirrors a microservices architecture. It decouples the monolithic task into three independent, specialized workers that run simultaneously, creating a self-maintaining and highly efficient data ecosystem. The key to its success is a priority system that creates an "express lane" for new and updated deals, ensuring they are processed immediately, ahead of the large, slow-moving backfill.

### Core Concept

The pipeline is split into three distinct jobs:
1.  **The Scout:** Discovers new deals and detects changes to existing ones.
2.  **The Processor:** Performs the heavy, time-consuming data enrichment.
3.  **The Refresher:** Periodically re-queues old deals to prevent staleness.

These workers operate in parallel. A priority system ensures that the most time-sensitive tasks (processing newly discovered deals) are always handled first, providing a "live" feel to the user-facing data at all times.

### Key Components

#### A. Evolved Database Schema

The `deals` table will be modified to support the new workflow. The following columns will be added:

*   `status` (TEXT): Tracks the deal's state. Values:
    *   `'pending_processing'`: The deal is in the queue to be enriched.
    *   `'active'`: The deal is fully processed and visible in the UI.
    *   `'archived'`: The deal no longer meets the base criteria.
*   `priority` (TEXT): Manages the processing order. Values:
    *   `'HIGH'`: An express-lane deal. A brand-new discovery or a live deal that has just changed.
    *   `'NORMAL'`: A standard-priority deal, typically part of the large backfill or a periodic refresh.
*   `last_full_update` (TIMESTAMP): Records the last time the Processor fully enriched the deal.
*   `created_at` (TIMESTAMP): Records when the deal was first discovered.

#### B. The "Scout" Worker

*   **Job:** To be the fast and efficient "eyes" of the system.
*   **Schedule:** Runs frequently (e.g., every 5 minutes).
*   **Actions:**
    1.  Makes a cheap API call to the Keepa `/deal` endpoint to get a list of the most recently changed deals.
    2.  For each ASIN returned, it checks the database:
        *   If the ASIN is **brand new**, it inserts a row with `status = 'pending_processing'` and `priority = 'HIGH'`.
        *   If the ASIN **already exists** and is `'active'`, it means a key stat (like price) has just changed. The Scout updates its record, setting `status = 'pending_processing'` and `priority = 'HIGH'`, pushing it into the express lane for an immediate update.
    3.  Separately, it works through the main, broad deal query page by page to discover the initial 15,000+ deals, inserting them all with `priority = 'NORMAL'`.

#### C. The "Processor" Worker

*   **Job:** To be the powerful but slow "brain" of the system, performing the heavy lifting.
*   **Schedule:** Runs continuously as a queue processor.
*   **Action:**
    1.  Queries the database for a small batch of deals using the critical `ORDER BY` clause: `SELECT * FROM deals WHERE status = 'pending_processing' ORDER BY priority DESC, created_at ASC LIMIT 10;`
    2.  This query guarantees that the Processor **always** handles all `'HIGH'` priority deals before it starts or resumes work on the massive `'NORMAL'` priority backfill queue.
    3.  For each deal, it performs all the expensive, time-consuming API calls (full product data, seller info, XAI analysis).
    4.  After processing, it updates the deal's row with the complete data, changes its status to `'active'`, and sets the `last_full_update` timestamp.

#### D. The "Refresher" Worker

*   **Job:** To ensure the long-term health and freshness of the entire database.
*   **Schedule:** Runs periodically (e.g., once a day).
*   **Action:**
    1.  Queries the database for `'active'` deals where `last_full_update` is older than a defined threshold (e.g., 7 days).
    2.  For these stale deals, it changes their status back to `'pending_processing'` and sets their `priority` to `'NORMAL'`. This automatically places them back into the slow-moving queue for a full, non-urgent update.

### Benefits of This Architecture

*   **No "Data Staleness" during Backfill:** The priority express lane ensures the user-facing data is always the freshest data available, even while a multi-week backfill is happening in the background.
*   **Immediate Time-to-Value:** The database becomes populated and usable within minutes of starting the system, growing organically over time.
*   **Extremely Scalable:** The Processor can be scaled to multiple concurrent workers to increase the throughput of the backfill and refresh cycles.
*   **Robust & Resilient:** If one component fails (e.g., the XAI service is down), it only affects the Processor. The Scout can continue discovering new deals, and the queue will be ready for when the Processor comes back online.
*   **Efficient API Usage:** Uses cheap API calls for frequent discovery and expensive calls only when necessary for targeted enrichment.