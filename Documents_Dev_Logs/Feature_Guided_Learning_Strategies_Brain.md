# Feature Documentation: Guided Learning, Strategies & Agent Brain (Admin Only)

This document details the functionality and logic for the AI-driven "Guided Learning" system, which extracts actionable strategies and conceptual ideas from external content and integrates them into the agent's knowledge base.

## Access Control

**Access Control:** These features (`/guided_learning`, `/strategies`, `/agent_brain`) are strictly **Admin-Only**.
*   **Authentication:** The system checks the user's role in the session (`session['role'] == 'admin'`).
*   **Enforcement:** Non-admin users attempting to access these routes are redirected to the Dashboard with an "Access Denied" error.
*   **Navigation:** Links to these pages are hidden from the navigation bar for non-admin users.

---

## 1. Guided Learning

**Route:** `/guided_learning` (Input), `/learn` (Processing), `/results` (Review), `/approve` (Storage)
**Templates:** `guided_learning.html`, `results.html`

### Overview
Guided Learning is the entry point for teaching the agent. The user provides a source of information (text, URL, or YouTube link), and the system uses Large Language Models (xAI Grok) to distill this information into structured knowledge.

### Workflow

1.  **Input (`/guided_learning`):**
    *   User pastes text or a URL into a form.
    *   Supports YouTube URLs (extracts transcript) and standard web pages (scrapes text).

2.  **Processing (`/learn`):**
    *   **Scraping:**
        *   If YouTube URL: Uses `youtube_transcript_api` (via BrightData proxy) to fetch the video transcript.
        *   If Web URL: Uses `httpx` and `BeautifulSoup` to scrape visible text, removing scripts/styles.
        *   If Text: Uses raw input.
    *   **AI Extraction (Parallelized):**
        *   The system sends the cleaned text to the xAI API in parallel threads.
        *   **Model:** Uses `grok-4-fast-reasoning` (Temperature 0.2-0.3) for high-speed, logical extraction.
        *   **Task A (Strategies):** Extracts actionable rules (numbers, thresholds, specific "if-then" logic).
        *   **Task B (Conceptual Ideas):** Extracts high-level mental models and "why" logic (The "Agent Brain").

3.  **Review (`/results`):**
    *   Displays the raw AI output for both Strategies and Conceptual Ideas.
    *   User can edit the text before approving.

4.  **Approval (`/approve`):**
    *   User clicks "Approve".
    *   The system parses the approved text (splitting by newlines).
    *   **Strategies** are appended to `strategies.json`.
    *   **Conceptual Ideas** are appended to `agent_brain.json`.
    *   Duplicates are removed automatically.

---

## 2. Strategies Page

**Route:** `/strategies`
**Template:** `templates/strategies.html`
**Data Source:** `strategies.json`

### Overview
Displays the repository of actionable rules the agent has "learned". These are specific, quantitative directives (e.g., "Buy if Sales Rank < 50,000 and Profit > $10").

### Logic
*   Reads the `strategies.json` file from the root directory.
*   Renders the list of strings/objects.
*   **Integration:** These strategies are injected into the context of the **"Advice from Ava"** feature (`ava_advisor.py`) to customize the AI's analysis of specific deals.

---

## 3. Agent Brain Page

**Route:** `/agent_brain`
**Template:** `templates/agent_brain.html`
**Data Source:** `agent_brain.json`

### Overview
Displays the "Mental Models" and high-level concepts the agent uses to understand the market. Unlike strategies, these are qualitative (e.g., "Textbooks have a U-shaped sales rank curve").

### Logic
*   Reads the `agent_brain.json` file from the root directory.
*   Renders the list of ideas.
*   This serves as the "System Prompt" or context for the agent's decision-making processes (e.g., when judging if a price is "reasonable" via AI).
