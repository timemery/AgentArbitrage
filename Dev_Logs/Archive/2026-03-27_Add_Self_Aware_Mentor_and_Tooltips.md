# Dev Log: Feature Self-Aware Mentor & Related Tooltips
**Date:** 2026-03-27

## Task Overview
The goal was to implement a "Self-Aware Mentor" feature and use this new platform knowledge to create AI-Triggered Hover Tooltips on the Deals Dashboard column headers and filters.

The process involved two core parts:
1.  **Self-Aware Mentor (Platform Knowledge)**: Create a module (`keepa_deals/platform_knowledge.py`) that reads specific Markdown documentation files from the `Documentation/` directory to act as a source of truth for the platform's logic and user interface. This knowledge needed to be injected into the existing `ava_advisor.py` prompts.
2.  **AI-Triggered Hover Tooltips**: Add contextual help triggers to the Deals Dashboard (`templates/dashboard.html`). When a user hovers over a table header or filter label, the system makes an API request to the AI (using the platform knowledge) to generate a succinct (max 150 character), "Verb + Noun" formatted explanation of that specific UI element.

## Challenges Faced

1.  **Table Width Constraints & UI Layout Breaking**: Initially, we added `?` icons next to each column header to act as the hover triggers. Because the Dashboard table has a strict `1200px` maximum width, adding this extra visual element to all 15+ columns pushed the table width out by about 150px, causing layout breaks and horizontal scrolling issues.
2.  **Tooltip Placement & UX Styling**: The initial tooltip implementation positioned the text to the bottom-right of the cursor. This felt disconnected and often obscured the data being explained. A "speech bubble" style (pointing directly at the hovered element from above or below) was requested instead.
3.  **API Latency (The "Hover Wait")**: Relying solely on real-time AI generation meant that users had to wait up to 3 seconds for a tooltip to appear after hovering. This violated the core UX principle that tooltips should provide *instant* feedback.
4.  **Complex Visual Indicators (Arrows)**: The AI needed to explain not just text labels, but also visual indicators like the red/green up/down arrows in the "Age" (last_price_change) and "Offers" columns, which standard OCR or text-based prompts often struggle with without explicit guidance.

## Solutions Implemented

1.  **Removed `?` Icons for Fluid Layout**: To fix the 1200px width constraint issue, we completely removed the `?` icons. Instead, we added the `ai-tooltip-trigger` class directly to the `<th>` (table headers) and `<label>` (filter labels) elements. We set `cursor: help` via CSS to indicate interactivity without consuming horizontal space.
2.  **Dynamic "Speech Bubble" Positioning**: We rewrote the JavaScript `positionTooltip` function in `dashboard.html`. It now calculates the bounding rectangle of the target element, centers the tooltip directly *above* the element (or below it if too close to the top of the viewport), and applies dynamic CSS classes (`arrow-top`, `arrow-bottom`). The CSS was updated with `::after` pseudo-elements to render a directional pointer.
3.  **Persistent Tooltip Caching**: We implemented a server-side JSON cache (`tooltip_cache.json`) in `ava_advisor.py`. Before querying the xAI API, the system checks this cache. If the tooltip exists, it returns immediately. Furthermore, we wrote and executed a one-off script (`pre_populate_tooltips.py`) to generate and cache all standard dashboard headers and filters, ensuring a 0ms wait time for end users on standard UI elements.
4.  **Explicit Prompt Engineering**: We updated the `generate_tooltip_advice` prompt in `ava_advisor.py` with a specific instruction: *"For arrows in columns like 'Age', explicitly mention their meaning based on documentation (e.g. Up = Price increased, Down = Price decreased)."* This forces the AI to cross-reference the `platform_knowledge` specifically for visual indicators.

## Outcome
**Success**. The tooltips now load instantly, are styled cleanly as speech bubbles above the target elements, and the strict 1200px table width is preserved. The AI mentor successfully utilizes the `Documentation/` folder as its source of truth, effectively mirroring documentation to the user dynamically without exposing underlying code mechanics.