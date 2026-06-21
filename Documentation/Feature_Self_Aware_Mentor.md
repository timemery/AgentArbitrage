# Feature Design: Self-Aware Mentor (Platform Knowledge)

## 1. Overview
The goal of this feature is to "train" the Mentor (Ava Advisor) to answer questions about how to use the AgentArbitrage.co platform itself (e.g., "How is profit calculated?", "What does the 'Drops' column mean?").

## 2. The Core Strategy: "Documentation Mirroring"

To solve the challenge of keeping the AI up-to-date with code changes without double-entry, we will implement a **Documentation Mirroring** strategy.

### The Concept
Since the `Documentation/` folder is already the source of truth for the system (and is manually updated by the developer), we will treat these Markdown files as the **Knowledge Base** for the Mentor. The Mentor will effectively "read the manual" before answering questions.

### Selected Source Files
We will configure the system to ingest specific user-facing documentation files:
1.  **`Documentation/Dashboard_Specification.md`**: Teaches the UI layout, columns, and filter logic.
2.  **`Documentation/Data_Logic.md`**: Teaches the math, formulas (Profit, Margin), and data sourcing pipeline.
3.  **`Documentation/Feature_Deals_Dashboard.md`**: Teaches the high-level features and workflows.
4.  **`Documentation/INFERRED_PRICE_LOGIC.md`**: Teaches the specific "Secret Sauce" logic for pricing.

### Why this works
*   **Zero Maintenance:** When you update `Data_Logic.md` to reflect a code change, the Mentor immediately "knows" it.
*   **Consistency:** The AI's answers will strictly align with the written documentation.
*   **Scalability:** Adding a new feature? Just document it (as you already do), and the Mentor learns it.

---

## 3. Technical Architecture

### A. New Module: `keepa_deals/platform_knowledge.py`
We will create a helper module responsible for reading and caching the documentation.

```python
# Pseudo-code logic
def load_platform_knowledge():
    sources = [
        'Documentation/Dashboard_Specification.md',
        'Documentation/Data_Logic.md',
        ...
    ]
    combined_knowledge = ""
    for file in sources:
        # Read file
        # Strip internal developer notes if necessary (optional)
        combined_knowledge += f"\n--- Section: {file} ---\n" + file_content

    return combined_knowledge
```

### B. Integration: `ava_advisor.py` & `wsgi_handler.py`
We will inject this knowledge into the Mentor's system prompt, alongside the existing `strategies.json` and `intelligence.json`.

**Revised Prompt Structure:**
```text
You are [Persona Name].

[Context: Strategy Knowledge Base]
...

[Context: Platform Documentation (How to use this tool)]
... {Content from Markdown Files} ...

[User Question]
...
```

To manage token limits, we can cache the "Platform Documentation" string in memory (reloading only when the `.md` files change, similar to the current caching strategy).

---

## 4. Frontend Integration: "Contextual Help" (Tool Tips)

To make this knowledge accessible, we will implement "Contextual Help" triggers in the UI.

### The Mechanism
Instead of static tooltips (which are hard to maintain and limited in length), we will use **AI-Triggered Help**.

1.  **UI Elements:** Add a small `?` icon or "Help" link next to complex features (e.g., the "Inferred Price" column header).
2.  **Action:** Clicking the icon opens the Mentor Chat window.
3.  **Payload:** The click automatically sends a specific, pre-written prompt to the Mentor.

**Example:**
*   **User clicks:** `?` next to "1yr Avg".
*   **System sends:** "Explain how the '1yr Avg' is calculated and why it might be missing."
*   **Mentor responds:** Uses the knowledge from `Data_Logic.md` to explain the logic (Mean of inferred sales, requires at least 1 sale, etc.).

### Implementation
We can add a simple generic JavaScript handler:
```html
<span class="help-icon" onclick="askMentor('How is the 1yr Avg calculated?')">?</span>
```

---

## 5. Summary of Workflow

1.  **Update:** You change the code and update `Documentation/Data_Logic.md`.
2.  **Deploy:** You deploy the changes.
3.  **Learn:** The system detects the file change (via timestamp check) and reloads the text into the Mentor's memory.
4.  **Answer:** A user asks "Why is my profit different?", and the Mentor answers using the exact formulas from your updated markdown file.
