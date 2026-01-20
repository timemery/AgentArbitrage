# UI Task Failure: Persistent Row Height & Sticky Header Issues
**Date:** January 19, 2026
**Status:** RESOLVED
**Topic:** Fixed Row Heights & Sticky Header Stability

## The Failure
This task marked a repeated failure (4+ attempts by different agents) to successfully implement a "Fixed Row Height" for the Deals Dashboard table.

**The Symptom:**
While the row height might appear correct when the page is static (at `scrollTop = 0`), the rows "squish", collapse, or misalign as soon as the user starts scrolling. The "sticky header" stack does not behave as a rigid, solid block. The shadow line jumps or floats incorrectly.

**The User Experience:**
The user explicitly requested "fixed row heights that never change". The agent interpreted this as "Set CSS `height: 56px`". The code was applied, but the *dynamic behavior* during scrolling was not verified, leading to the "squishing" effect persisting.

## Root Cause Analysis
1.  **Static vs. Dynamic Verification:**
    - The agent verified the changes by taking a static screenshot. In a static state, `height: 56px` looks correct.
    - The agent failed to verify the *scroll interaction*. The "squishing" only happens when the sticky positioning logic engages during a scroll event. Without a video or a scroll-based comparison test, the failure was invisible to the agent until the user pointed it out.

2.  **The "Table" Trap:**
    - The dashboard uses a standard HTML `<table>` with `position: sticky` on `<th>` elements.
    - Browsers handle table borders and cell heights differently than `div` blocks. When a `th` becomes sticky, its relationship with the row border can glitch, causing 1px shifts that look like "squishing".
    - Calculated `top` offsets (e.g., `calc(var(--filter-panel-height) + 134px)`) must match the *rendered* pixel height exactly. If the browser renders 56.5px or includes a 1px border that wasn't calculated, the stack collapses visually.

3.  **Semantic Misinterpretation:**
    - **User Meaning:** "Fixed" = Rigid, immovable, like a native app header.
    - **Agent Meaning:** "Fixed" = `height: 56px` or `position: fixed`.
    - **Gap:** The agent solved for the CSS property, not the user interface stability.

## Resolution
**Date Resolved:** January 19, 2026

The issue was successfully resolved by identifying that **external margins** on the sticky containers were the primary culprit for the dynamic "squishing" behavior.

**The Fix:**
1.  **Removed External Margins:**
    -   Removed `margin-top: 15px` from `.filter-panel`.
    -   Removed `margin: 24px auto 0 auto` from `#deals-table`.
    -   *Why:* Margins do not collapse in the same way for sticky elements as they do for static ones. When scrolling started, the browser would attempt to "reclaim" the margin space, causing the elements to jump or compress visually.

2.  **Enforced Rigid Heights:**
    -   Applied `height`, `min-height`, and `max-height` with `!important` to all header rows.
    -   **Group Header:** 56px.
    -   **Column Header:** 34px.
    -   **Sort Arrows:** 24px.
    -   *Why:* This forces the browser to respect the exact pixel dimensions regardless of content or sticky state.

3.  **Corrected Vertical Alignment:**
    -   Set `line-height: 1.2 !important` and `vertical-align: middle !important` for Column Headers.
    -   *Why:* Previously, the text was sticking to the bottom of the cell during the sticky state due to default table cell alignment and padding interactions.

4.  **Recalculated Offsets:**
    -   Updated the `top` calculation for every sticky layer to exactly match the sum of the preceding rigid heights.

**Lesson Learned:**
When debugging sticky header issues in tables, **always check for margins** on the container elements first. CSS Sticky positioning is extremely sensitive to the box model, and external margins often cause unexpected layout shifts during the transition from static to sticky.
