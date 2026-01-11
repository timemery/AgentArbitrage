# Refiller Analysis and Next Steps

**Date:** 2026-01-13
**Status:** In Progress / Concept Phase

## The Goal
We want to observe the **Refiller** (`update_recent_deals`) in action in isolation. The Refiller is designed to be the high-speed "Delta Sync" engine, checking for updates every minute.

To achieve this, we attempted to use an **"Artificial Backfill Limit"** to stop the Backfiller (the heavy, slow engine) once the database reached a certain size (e.g., 3000 deals). The hypothesis was that with the Backfiller stopped, the Refiller would take over maintenance.

## The Problem (Deal Decay)
When the Backfiller stops, the deal count on the dashboard drops rapidly (e.g., from 3000 to 300 in a day).

**Root Cause:**
1.  **Dependency:** The Refiller only updates deals that have *changed* on Keepa (Delta Sync). It does not touch "static" deals.
2.  **The Janitor:** The Janitor deletes any deal with `last_seen_utc > 72 hours`.
3.  **The Conflict:** The Backfiller is the *only* process that iterates through *all* deals (even static ones) and updates their `last_seen_utc`. When we stop the Backfiller, static deals age out and get deleted by the Janitor.

## Failed Approaches

### 1. Maintenance Mode (Rejected)
*   **Idea:** Keep the Backfiller running but only process existing deals.
*   **Result:** It works to keep deals alive, but it forces the Refiller and Backfiller to run concurrently. This is complex (locking issues) and resource-intensive (double token consumption). It defeats the purpose of "Observing the Refiller in isolation".

### 2. Pausing the Janitor (Rejected)
*   **Idea:** Stop the Janitor from deleting deals when the Backfill Limit is active.
*   **Result:** This preserves the deal count, but the database fills with "Zombie Deals". A deal might have a `last_seen_utc` of 10 days ago. The price in our DB might be $50, but the real price is now $10. We are no longer testing a "Live System", but a "Frozen Snapshot".

## Recommended Next Steps

We need a dedicated **"Simulation Mode"** or a structural change that allows the Refiller to handle "Keep Alives" without scanning the entire Keepa database.

### Option A: The "Touch" Refiller
Modify the Refiller logic. Instead of just querying for *changes*, it could also query for a batch of the "oldest" ASINs in our local DB just to refresh them.
*   **Pros:** True self-sustaining system.
*   **Cons:** Increases Refiller complexity and token cost.

### Option B: Accept the Decay
If the goal is to see *active* deals, maybe we accept that static deals die?
*   **Counter-argument:** 300 deals is too small a sample size to be useful.

### Option C: The "Ping" Service
A lightweight task that just runs `GET /product` on our local inventory every 48 hours to update `last_seen_utc`.
*   **Pros:** Simple, decouples maintenance from discovery.
*   **Cons:** New architectural component.

**Decision:** We are closing the current task to rethink the strategy rather than pushing "hacky" fixes into the production codebase.
