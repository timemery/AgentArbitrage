# UI Task Failure: Persistent Row Height & Sticky Header Issues
**Date:** January 19, 2026
**Status:** FAILED
**Topic:** Fixed Row Heights & Sticky Header Stability

## The Failure
This task marks a repeated failure (4+ attempts by different agents) to successfully implement a "Fixed Row Height" for the Deals Dashboard table. 

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

## CRITICAL WARNING TO NEXT AGENT
**DO NOT** simply apply `height: 56px` and mark the task as done. This has been tried and failed multiple times.

**To succeed, you must:**
1.  **Acknowledge the Difficulty:** Sticky table headers are fragile. Consider if the architecture needs to change (e.g., separating the Header into a distinct `div` outside the `table`) to achieve true rigidity.
2.  **Verify Dynamically:** You **cannot** verify this task with a single screenshot. You must verify that the header stack height is *identical* at `scrollTop=0` and `scrollTop=100`.
3.  **Respect the "Squish":** If the user says it squishes, it implies the sticky stack is compressing. Check your `z-index` layering and `top` offset math. It must be pixel-perfect, accounting for every border.

**Recommendation for Next Attempt:**
Stop trying to force the `<table>` to behave. Move the "Group Headers", "Column Headers", and "Sort Arrows" *out* of the `<table>` and into a separate, fixed container `div` that sits above the scrollable table body. This is the only reliable way to ensure they "never move or get squished."
