# Dev Log: Add Counting Feature to Strategies & Intelligence

**Date:** 2026-02-04
**Author:** Jules (AI Agent)
**Status:** Successful
**Task:** Implement "Total" and "New Today" counters for the Strategy and Intelligence databases to help track knowledge saturation.

## 1. Overview

The goal of this task was to provide users with a visual indication of how much *new* information is being gathered daily versus the total historical knowledge base. This helps answer the question: "Have we found everything yet?" If "New Today" consistently drops to zero despite active sourcing, it indicates saturation.

To achieve this, the system needed to track *when* each item was added to the database.

## 2. Architecture & Data Changes

### Data Structure Migration
Previously, `intelligence.json` was a simple list of strings. To support tracking, this was migrated to a list of objects. `strategies.json` (already a list of objects) was augmented with a new field.

*   **Intelligence Schema:**
    *   **Old:** `["Idea 1", "Idea 2"]`
    *   **New:** `[{"content": "Idea 1", "date_added": "2026-02-04"}, ...]`

*   **Strategies Schema:**
    *   Added `date_added`: "YYYY-MM-DD" field to existing strategy objects.

A migration script (`migrate_data_for_counting.py`) was created and executed to upgrade existing production data without data loss, setting the default date for existing items to today.

### Backend Logic (`wsgi_handler.py`)
*   **Counting:** The `/strategies` and `/intelligence` routes now iterate through the loaded JSON data to calculate:
    *   `total_count`: Total number of entries.
    *   `new_today_count`: Number of entries where `date_added` matches `datetime.now().strftime('%Y-%m-%d')`.
*   **Deduplication:** The `_deduplicate_strategies` and `_deduplicate_intelligence` functions were rewritten to:
    1.  Handle the new object formats.
    2.  **Crucially:** Preserve the `date_added` of the *surviving* item. If duplicates exist (one old, one new), the logic preserves the first instance found (typically the older one if appended sequentially), ensuring we don't artificially inflate "New Today" by re-adding old ideas.

### Maintenance Tasks (`keepa_deals/maintenance_tasks.py`)
The `homogenize_intelligence_task` (which uses LLM to merge similar ideas) presented a unique challenge.
*   **Challenge:** The LLM takes a list of strings and returns a new list of strings (merged/cleaned). It doesn't know about the original `date_added`. If we simply saved the LLM output as new objects, *every* item would look "New Today" after a homogenization run, destroying the history.
*   **Solution:**
    1.  Before calling the LLM, the task builds a `content_date_map` (`{content_string: original_date}`).
    2.  After the LLM returns the cleaned strings, the task checks the map.
    3.  **Match:** If the cleaned string matches an existing input, the *original* date is restored.
    4.  **No Match:** If the string is new (a merged concept or rewrite), it gets today's date.

### AI Advisor (`keepa_deals/ava_advisor.py`)
Updated `load_intelligence()` to parse the new object structure (`item['content']`) so the AI Mentor can still access the knowledge base.

## 3. Challenges & Solutions

| Challenge | Solution |
| :--- | :--- |
| **Legacy Data Formats** | Created a robust migration script that handled both dictionaries (strategies) and raw strings (intelligence), ensuring a smooth transition to the new schema. |
| **Homogenization Resetting Dates** | Implemented the "Map-Reduce-Restore" pattern in `homogenize_intelligence_task`. By mapping content to dates *before* processing, we ensured that existing ideas kept their history even after being passed through the cleaning pipeline. |
| **Frontend Verification** | Used Playwright to verify that the "New Today" counts appeared correctly on the dashboard. Initial tests failed due to strict locator issues, which were resolved by using more specific text locators. |

## 4. Outcome

The task was **successful**.
*   Users can now see "XXX Strategies / XXX New Today" on the UI.
*   The "New Today" count accurately reflects true new additions.
*   Running "Remove Duplicates" or "Homogenize" updates the total count but preserves the historical context of remaining items.
