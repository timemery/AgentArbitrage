# Task Description: Feature Self-Aware Mentor & Related Tooltips

This task involves implementing two related features for the AgentArbitrage.co platform: the "Self-Aware Mentor" (Platform Knowledge) and "AI-Triggered Hover Tooltips" on the Deals Dashboard.

These two features are grouped into a single task because they are deeply intertwined. The dynamic tooltips rely directly on the Mentor's ability to read and understand the platform's documentation (the "Self-Aware" feature).

## 1. Feature: Self-Aware Mentor (Platform Knowledge)

The goal is to "train" the Mentor (Ava Advisor) to answer questions about how to use the AgentArbitrage platform itself (e.g., "How is profit calculated?", "What does the 'Drops' column mean?").

### The Core Strategy: "Documentation Mirroring"
We will use the `Documentation/` folder as the source of truth for the Mentor to avoid double-entry. The Mentor will effectively "read the manual" before answering questions.

**Selected Source Files:**
1.  **`Documentation/Dashboard_Specification.md`**: Teaches UI layout, columns, and filter logic.
2.  **`Documentation/Data_Logic.md`**: Teaches math, formulas (Profit, Margin), and data sourcing pipeline.
3.  **`Documentation/Feature_Deals_Dashboard.md`**: Teaches high-level features and workflows.
4.  **`Documentation/INFERRED_PRICE_LOGIC.md`**: Teaches the specific logic for pricing.

### Technical Architecture
*   **New Module:** Create `keepa_deals/platform_knowledge.py` to read and cache the selected documentation files.
*   **Integration:** Inject this combined knowledge into the Mentor's system prompt in `ava_advisor.py` (and potentially `wsgi_handler.py`), alongside existing strategies and intelligence.
*   **Security Constraint:** Ensure the prompt strictly limits the AI from explaining *how the code works* to prevent reverse-engineering or exposing the internal "guided learning" features. It must only explain *how to use the tool* based on the provided documentation.

## 2. Feature: Hover "Tool Tips" on Dashboard Column Headers & Filters

We need to implement "Contextual Help" triggers in the UI, specifically on Dashboard column headers and filters, to explain what each item is, does, and means.

### AI-Triggered Tooltips
Instead of static, hardcoded tooltips, we will use **AI-Triggered Help** written and managed by xAI (Grok), leveraging the "Self-Aware Mentor" logic implemented in part 1.

**The Mechanism:**
1.  **UI Elements:** Add a small `?` icon or "Help" visual indicator next to column headers (e.g., "% ⇩", "Now", "1yr Avg") and filters.
2.  **Action:** Hovering over or clicking the indicator triggers the help content.
3.  **Payload:** The system automatically sends a specific prompt to the Mentor (e.g., "Explain how the '1yr Avg' is calculated.").
4.  **Response:** The Mentor uses the `platform_knowledge.py` context to explain the logic.

### Tooltip Content Guidelines (CRITICAL for UX)
The AI must be strictly prompted to format its tooltip responses according to these rules:
*   **Be Succinct:** The best tooltips are 2–5 words. Provide immediate, scannable clarity.
*   **Character Limits:** Aim for **20–30 characters** (a single short phrase). **Absolute Maximum is 150 characters** (approx. 2 sentences).
*   **No "Walls of Text":** Do not exceed 3 lines. If it covers critical UI, it's too long.
*   **Focus on One Idea:** Explain a single action or define a term, not the whole feature.
*   **Format:** Use **Sentence case**. Generally friendlier and easier to read.
*   **Style:** Use **"Verb + Noun"** when applicable (e.g., "Search by image").
*   **Non-Redundant:** Do not just repeat the visible label.
*   **Alternatives:** If the explanation requires >150 chars, links, or images, the UI should use a popover or open the Mentor Chat window instead of a standard tooltip.

## ⚠️ IMPORTANT INSTRUCTIONS FOR THE AGENT

**Start with a fresh, high-performance sandbox.**
This is critical to avoid environmental instability on long tasks. Requesting a "fresh" sandbox is a critical initial step.

**Note on Environment Secrets (.env):**
The `.env` file is excluded from the repository. It is a critical dependency. You must **recreate this file** in your sandbox environment at the start of the task using the secrets provided in the environment setup details. The application will not function without it.

**READ these files:**
- `README.md`
- `AGENTS.md`
- `Documentation/System_State.md`
- `Documentation/Data_Logic.md`
- `Documentation/Dashboard_Specification.md`
- `Documentation/Token_Management_Strategy.md`
- `Documentation/System_Architecture.md`
- `Documentation/Feature_Deals_Dashboard.md`
- `Documentation/Feature_Guided_Learning_Strategies_Brain.md`
- `Documentation/INFERRED_PRICE_LOGIC.md`
- The 3 most recent Dev Logs in `Dev_Logs/`

**Do NOT Read these files:**
- Do NOT read `xai_cache.json`, `strategies.json`, `agent_brain.json`
- Do NOT read `*.log` files
- Do NOT read `Diagnostics/`
- Do NOT read `tests/`
- Do NOT read `AgentArbitrage_BeforeGateCheckFeature2/`
- Do NOT read `RAW_PRODUCT_DATA.md` or **ANY** other historical documents unless specifically requested
- Do NOT read any `*.log` file of any kind unless specifically requested
- Do NOT read any files in any `Archive/` directories unless specifically requested
