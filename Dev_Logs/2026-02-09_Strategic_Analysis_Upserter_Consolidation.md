# Strategic Analysis: Upserter Consolidation

## Task Overview
The objective was to analyze the feasibility of consolidating the deal ingestion pipeline into a single "Upserter-Only" model, effectively removing the `Backfiller` (`backfiller.py`) to streamline operations and eliminate token starvation. The core question was whether the `Upserter` (`simple_task.py`) could be enhanced to handle all data collection duties without sacrificing critical "safety net" features provided by the Backfiller.

## Challenges & Analysis
### 1. Token Starvation & Livelock
Historical logs revealed that running two heavy tasks (Upserter & Backfiller) simultaneously on a low-tier Keepa plan (<20 tokens/min) caused severe resource contention. The Backfiller would consume all available tokens on "deep scans" of old data, starving the Upserter and preventing it from capturing new, live deals. This led to a "stuck" dashboard count (~275 deals) where the system was busy but unproductive.

### 2. Missing "Safety Nets" in Upserter
A deep dive into `backfiller.py` revealed three critical features that `simple_task.py` lacked:
*   **Zombie Data Repair:** The Backfiller actively detects and repairs corrupted rows (e.g., missing `List Price` or `1yr Avg`). The Upserter does not; it either saves valid data or ignores the deal, leaving broken rows in the DB forever.
*   **Ghost Restriction Recovery:** The Backfiller re-processes deals stuck in "Pending" restriction status due to silent failures. The Upserter triggers the check but has no retry mechanism.
*   **Incremental State Saving:** The Backfiller saves its progress every 4 deals. The Upserter only updates the watermark at the very end of a run. A crash on deal 199/200 in the Upserter causes a full restart (Loop of Death), whereas the Backfiller would resume from deal 200.

### 3. The "Peek Strategy" Optimization (365 Days)
The Backfiller initially used a "Two-Stage Fetch":
1.  **Stage 1 (2 Tokens):** Fetch history. Filter for profitability.
2.  **Stage 2 (20 Tokens):** Fetch full history only if Stage 1 passes.

**Analysis of Keepa API Costs:**
We verified that fetching `stats=365` costs the same as `stats=90` (approx 2 tokens) as long as `history=0` (no CSV data) is requested.
*   **Old Strategy:** Peek at 90 days. Risk: Miss seasonal items (False Negatives).
*   **New Strategy:** Peek at **365 days** (`stats=365`). Benefit: Eliminates the "90-Day Blind Spot" for the same low cost, allowing accurate seasonality filtering before committing to the expensive fetch.

### 4. Technical "Gotchas"
*   **Sort Order Rigidity:** The Upserter relies on `Sort Type 4` (Last Update) to maintain its watermark. Analysis of `keepa_api.py` confirmed that `fetch_deals_for_deals` hardcodes `sortType=4`, mitigating this risk.
*   **AI Rejection Rate:** The current logic (`stable_calculations.py`) often rejects valid low-priced deals because they deviate from a high 3-year average. A requirement was added to **bypass the AI check** if the calculated price is capped by the Amazon New Price (the "Amazon Ceiling").

## Solutions Implemented
*   **Theoretical Verification:** Confirmed that an "Upserter-Only" model is viable IF the missing features (Peek Strategy, Zombie Repair, Incremental Saves, AI Bypass) are ported.
*   **Architecture Plan:** Created `Refactor_Plan.md` detailing the blueprint for the new `Smart_Ingestor` component, explicitly specifying `stats=365` for the peek strategy.
*   **Documentation:** Recorded all "Past Demons" (Livelocks, Loops, Ghost Data) to ensure the future implementation specifically defends against them.

## Outcome
**SUCCESS.** The analysis confirmed the path forward. No code was changed in this task, but the roadmap (`Refactor_Plan.md`) provides a safe, detailed guide for the refactoring. The plan includes archiving legacy components and renaming the new component to `Smart_Ingestor` to reflect its expanded capabilities.
