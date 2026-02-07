# Technical Documentation: Inferred Price Calculation Logic

## 1. Overview

This document details the system used to calculate the **List at** (Peak), **Trough**, and **1-Year Average** prices for a given product (ASIN). The entire system is predicated on the concept of an "inferred sale," which is a historical moment where data strongly suggests a transaction occurred.

The primary logic is housed in:
- `keepa_deals/stable_calculations.py`
- `keepa_deals/new_analytics.py`

The process follows three main stages:
1.  **Inferring Sale Events** (Finding the data points).
2.  **Sanitization** (Removing noise).
3.  **Calculation & AI Validation** (Determining the final prices).

------

## ⚠️ Critical Warning: The Dangers of Fallback Data

**Do NOT attempt to "fill in the blanks" with unverified data.**

A critical lesson learned in January 2026 is that fallback mechanisms—attempts to provide a price when the primary logic finds none—are extremely dangerous. They often result in the system confidently presenting garbage data, which then triggers downstream rejections (like the AI Reasonableness Check) or, worse, leads users to make bad buying decisions.

**Specific Failure Case: The "High Velocity" Fallback**
The system previously contained a fallback logic:
> *If no sales are inferred, but `monthlySold > 20`, use the `Used - 90 days avg` price.*

This caused massive deal rejection rates (~95%) because:
1.  `monthlySold` measures **Total** velocity (New + Used).
2.  `avg90` (Used) measures the **Used** price history.
3.  **Scenario:** A book sells briskly as New ($50) but has a stale, high-priced Used listing ($400) that never sells.
4.  **Result:** The fallback sees high velocity (from New sales) and erroneously grabs the high Used price ($400).
5.  **Impact:** The system sets "List at" to $400. The AI check correctly rejects "$400 for this book". The deal is discarded.

**Principle:** If the system cannot find a price through **confirmed inferred sales** (Offer Drop + Rank Drop), it should return `None` (missing data) rather than guessing. Accuracy is prioritized over completeness.

------

## 2. Stage 1: Inferring Sale Events

This is the foundational step handled by `infer_sale_events(product)` in `keepa_deals/stable_calculations.py`.

### a. The "Sale" Trigger and Confirmation
A sale is inferred by correlating two distinct events within a **240-hour** (10-day) window over the last two years:

1.  **The Trigger:** A drop in the offer count for either **New** or **Used** listings.
    -   Source: `csv[11]` (New Count) and `csv[12]` (Used Count).
    -   Mechanism: `diff()` detects negative changes.
2.  **The Confirmation:** A drop in the product's **Sales Rank** (`csv[3]`).
    -   Rationale: A rank drop indicates Amazon registered a sale.
    -   Window: If a rank drop occurs within 240 hours *after* an offer count drop, it is flagged as a confirmed sale.

### b. Price Association
When a sale is confirmed, the system associates a price with it using `pandas.merge_asof`. It finds the nearest listing price from the history (`new_price_history` or `used_price_history`) at the exact time of the sale.

------

## 3. Stage 2: Data Sanitization

After collecting raw events, the data is sanitized to remove statistical outliers.

### Symmetrical Outlier Rejection
To prevent anomalous prices (e.g., penny books or repricer errors) from skewing the results:
1.  Calculates **Q1** (25th percentile) and **Q3** (75th percentile) of all inferred prices.
2.  Calculates **IQR** (Interquartile Range).
3.  Removes any sale price outside the range `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`.
4.  **Result:** A list of "sane" sale events.

------

## 4. Stage 3: Price Calculation

### A. The "List at" Price (Peak Season)
This determines the recommended listing price.

1.  **Seasonality Identification:** Groups sane sales by month. Identifies the **Peak Month** (highest median price).
2.  **Price Determination:**
    -   **Primary:** Calculates the **Mode** (most frequent price) during the Peak Month.
    -   **Fallback 1:** If no distinct mode exists, uses the **Median**.
    -   **Fallback 2 (High Velocity):** **REMOVED**. See Critical Warning above.
3.  **Amazon Ceiling Logic:**
    -   To ensure competitiveness, the "List at" price is capped at **90%** of the lowest Amazon "New" price.
    -   Comparator: `Min(Amazon Current, Amazon 180-day Avg, Amazon 365-day Avg)`.
    -   If `List at > Ceiling`, it is reduced to the Ceiling value.
4.  **AI Reasonableness Check:**
    -   The calculated price, along with the book's title, category, **Binding**, **Page Count**, **Image URL**, and **Rank**, is sent to **xAI (Grok)**.
    -   Prompt: "Is a peak price of $X.XX reasonable for [Book Title]?"
    -   **Prompt Context:** The prompt explicitly instructs the AI that for seasonal items (especially Textbooks), a Peak Season price can validly be **200-400% higher** than the 3-Year Average to prevent false positive rejections.
    -   If the AI rejects it (returns "No"), the deal is discarded.

### B. 1-Year Average (`1yr. Avg.`)
Used for the "Percent Down" and "Trend" calculations.

1.  Filters the sane sales list to include only those from the **last 365 days**.
2.  Calculates the **Mean** of these prices.
3.  **Threshold:** Requires at least **1** inferred sale. If 0, returns `None` (Deal excluded).

------

## Key Evolution & "Hard-Won" Lessons

1.  **Mean vs Median:** We switched from Median to **Mean** for the 1-Year Average to better reflect the true market value across all transactions, after outlier removal proved effective.
2.  **Mode for Peak:** We use **Mode** for the "List at" price because arbitrage sellers often target a specific "standard" market price that occurs frequently, rather than an average of fluctuations.
3.  **Strict Validation:** The AI check and the "Missing List at" exclusion are the primary filters. If the system cannot confidently determine a safe listing price, it prefers to reject the deal rather than present a risky one.
4.  **240-Hour Window:** Expanding the correlation window from 168h to 240h significantly improved capture rates for "Near Miss" sales events where rank reporting lagged behind offer drops.

------

## 5. Verification Case Study: The "Missing Data" Investigation (Feb 2026)

In February 2026, users reported that several deals appeared on the dashboard with missing data (e.g., `1yr Avg: -`) or negative profit, despite Keepa data seemingly being available. An in-depth investigation was conducted to determine if the *calculation logic* was flawed.

### Methodology
A diagnostic script (`tests/trace_1yr_avg.py`) was created to trace the exact execution of the logic on ASIN `1455616133`, one of the reported "missing data" items.

### Findings
1.  **Raw History:** The script found 1286 rank history points and 100 offer count points (valid data availability).
2.  **Inference Logic:**
    *   Detected **46** raw offer drops.
    *   Successfully correlated **28** of them with a Rank Drop within the 240-hour window.
3.  **Sanitization:** 8 outliers were removed using the IQR method.
4.  **Result:**
    *   **Sales in Last 365 Days:** 28 confirmed sales.
    *   **Calculated 1yr Avg:** **$54.38**.

### Conclusion
The calculation logic is **sound**. The data *does* exist, and the algorithm *can* find it. The reason these deals appeared broken on the dashboard was **Data Ingestion Stagnation** (deals getting stuck in a "lightweight update" loop that never re-fetched the full history needed for the calculation), not a flaw in the math itself.

### Resolution
Instead of changing the math (e.g., adding unsafe fallbacks), we implemented a **"Self-Healing Backfill"** strategy. The system now detects these "Zombie" deals (missing data) and forces a full re-fetch to allow the proven logic to execute correctly.
