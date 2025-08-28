# Agent Arbitrage Project Plan

## 1. Project Overview

**Objective:** To create a semi-autonomous AI agent that can learn to identify profitable books for online arbitrage, and a web application to manage and interact with the agent.

**Phases:**

*   **Phase 1: Minimum Viable Product (MVP)**
    *   **1A: AI Agent Development:** Focus on core data processing and the "Guided Learning" module.
    *   **1B: Web Interface Development:** Build a basic web interface for interaction and data visualization.
*   **Phase 2: Demo Mode Simulation:** Simulate buying and selling books to test the agent's logic.
*   **Phase 3: Web Application V1:** Develop a subscriber-accessible web application.
*   **Phase 4: Semi-Autonomous AI Agent:** Integrate with Amazon's API for real-world actions.
*   **Phase 5: Full Autonomy and Scaling:** Enhance the agent's learning capabilities and scale the system.

---

## 2. Phase 1: Minimum Viable Product (MVP)

### Phase 1A: AI Agent Development (Weeks 1-6)

**Week 1: Setup and Foundation**

*   [ ] Set up the Python environment on the cPanel server.
*   [ ] Clone the new Agent Arbitrage GitHub repository.
*   [ ] Install initial dependencies: `pandas`, `numpy`, `requests`, `beautifulsoup4`, `flask`.
*   [ ] Create a basic Flask application structure.

**Week 2-3: The "Guided Learning" Module**

*   [ ] Build a simple web form to submit URLs and text for learning.
*   [ ] Create a Python script to scrape content from URLs using `BeautifulSoup`.
*   [ ] Integrate a lightweight LLM (via Hugging Face API) to:
    *   [ ] Summarize scraped text.
    *   [ ] Extract key strategies and parameters (e.g., "sales rank between X and Y").
    *   [ ] Add support for extracting transcripts from YouTube videos.
*   [ ] Create an interface to review, edit, and approve the extracted rules.

**Week 4-5: Core Data Processing and Rule-Based Engine**

*   [ ] Develop a data pipeline to read and parse Keepa CSV data using `pandas`.
*   [ ] Build a rule-based engine that uses the curated rules from the "Guided Learning" module to analyze Keepa data.
*   [ ] Implement the profit calculation logic, including all fees.
*   [ ] Generate a CSV output of profitable ASINs.

**Week 6: Initial Integration and Communication**

*   [ ] Connect the "Guided Learning" module to the rule-based engine.
*   [ ] Build a simple communication interface (e.g., a chat or Q&A form) in the Flask app to query the agent's status and learned rules.

### Phase 1B: Web Interface and Refinement (Weeks 7-10)

**Week 7: Backend Refactoring and Database Integration**

*   [ ] Refactor the data processing scripts to be more server-friendly.
*   [ ] Set up a MySQL database on the cPanel server.
*   [ ] Store the Keepa data in the MySQL database for more efficient querying.

**Week 8: Front-End Expansion**

*   [ ] Expand the Flask UI using Bootstrap for a more user-friendly dashboard.
*   [ ] Display the list of profitable deals in a clean, readable format.
*   [ ] Add input forms for user settings (e.g., prep fees, markup).

**Week 9: End-to-End Integration and Testing**

*   [ ] Ensure all components (Guided Learning, data processing, UI) work together smoothly.
*   [ ] Conduct thorough testing of the entire workflow.
*   [ ] Debug and fix any issues that arise.

**Week 10: Deployment and Documentation**

*   [ ] Deploy the Flask application on the cPanel server using Apache and WSGI.
*   [ ] Write a user guide on how to use the application.
*   [ ] Write a developer guide explaining the different components of the system.
*   [ ] Update the GitHub repository with the final code and documentation.

### Phase 1C: Data Presentation and Configuration (Evolution from original plan)

**Objective:** To build the necessary UI components for managing application settings and viewing the collected data, which is a prerequisite for the AI analysis phase.

*   **Settings Page / Dashboard:**
    *   [ ] Create a secure page for users to input and manage essential information.
    *   [ ] Form fields for API Keys (Keepa, Amazon SP-API).
    *   [ ] Form fields for user-specific business costs (e.g., prep fees, shipping costs, desired profit margin).
    *   [ ] Implement backend logic to securely store and retrieve these settings.

*   **Raw Data Viewer:**
    *   [ ] Develop a new page to display the contents of the `Keepa_Deals_Export.csv` file.
    *   [ ] Present the data in a clean, sortable HTML table.
    *   [ ] This provides transparency and allows the user to inspect the raw data before AI analysis.

*   **Analyzed Deals View:**
    *   [ ] Design and implement a page where the AI will present its findings.
    *   [ ] This view will only show deals that the AI has determined to be profitable, based on the user's learned strategies and configured costs.
    *   This is the core "hands-off" value proposition of the application.

---

## 3. Future Phases

*   **Phase 2: Demo Mode Simulation:** Implement a demo mode to simulate buying and selling books without real transactions.
*   **Phase 3: Web Application V1:** Develop a subscriber-accessible web application with user authentication and subscription management.
*   **Phase 4: Semi-Autonomous AI Agent:** Integrate with Amazon's Selling Partner API (SP-API) to allow the agent to perform real-world actions.
*   **Phase 5: Full Autonomy and Scaling:** Enhance the agent's learning capabilities to adapt to market trends and scale the system to handle more users and products.

### Future Architecture: "Listen and Update" Model

As an alternative to the batch-processing model, a more advanced architecture can be implemented for real-time updates. This involves:
*   **Persistent Database:** Migrating from CSV files to a structured database (e.g., MySQL, PostgreSQL) to store a master list of all known deals.
*   **Background Worker/Daemon:** A standalone, persistent process that runs 24/7 on the server.
*   **Intelligent Polling:** The worker will be responsible for all Keepa API interactions. It will periodically poll the `/deal` endpoint for new ASINs to add to the database. It will also intelligently re-check existing ASINs in the database to get the latest price and rank data.
*   **Live Web Dashboard:** The web application will read directly from the database, providing users with a constantly up-to-date view of the available deals without needing to manually run a scan.

This architecture represents a significant increase in complexity but is the ideal model for a production-level, "always-on" service. It is recommended to pursue this after the core features of the MVP (data collection, settings, and AI analysis) have been validated.

---

## 4. Key Considerations

*   **Beginner-Friendly Approach:** The plan is designed to be achievable for a beginner, with a focus on simple tools and AI-assisted development.
*   **Server and Deployment:** The initial development will be on the existing cPanel server, but we should be prepared to migrate to a more robust hosting solution in the future.
*   **"Guided Learning":** The AI's learning will be guided by the user, who will provide resources and approve the extracted rules.
*   **User Interface:** The user interface will be developed with a focus on usability and a clear user flow.
*   **Code Management:** The project will be developed in a separate repository to keep the code clean and organized.

---

## 5. Postponed Tasks

### YouTube Transcript Scraping

*   **Status:** Partially Implemented, Currently Non-Functional.
*   **Issue:** The feature to extract transcripts from YouTube videos is currently broken. After a lengthy debugging process, the root cause appears to be a persistent, unresolvable bug related to either the `youtube-transcript-api` library, the server environment, or a discrepancy in the code visible to the agent. The feature was refactored from a Selenium-based approach to use the API, but a final `AttributeError` could not be resolved despite the code appearing correct on the server.
*   **Decision:** To maintain project momentum, the decision has been made to postpone fixing this feature. The non-functional code remains in the repository.
*   **Next Steps:** This feature should be revisited at a later stage in the project, potentially after major components are complete or if a new approach is discovered.