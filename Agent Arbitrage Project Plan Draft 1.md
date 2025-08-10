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

---

## 3. Future Phases

*   **Phase 2: Demo Mode Simulation:** Implement a demo mode to simulate buying and selling books without real transactions.
*   **Phase 3: Web Application V1:** Develop a subscriber-accessible web application with user authentication and subscription management.
*   **Phase 4: Semi-Autonomous AI Agent:** Integrate with Amazon's Selling Partner API (SP-API) to allow the agent to perform real-world actions.
*   **Phase 5: Full Autonomy and Scaling:** Enhance the agent's learning capabilities to adapt to market trends and scale the system to handle more users and products.

---

## 4. Key Considerations

*   **Beginner-Friendly Approach:** The plan is designed to be achievable for a beginner, with a focus on simple tools and AI-assisted development.
*   **Server and Deployment:** The initial development will be on the existing cPanel server, but we should be prepared to migrate to a more robust hosting solution in the future.
*   **"Guided Learning":** The AI's learning will be guided by the user, who will provide resources and approve the extracted rules.
*   **User Interface:** The user interface will be developed with a focus on usability and a clear user flow.
*   **Code Management:** The project will be developed in a separate repository to keep the code clean and organized.