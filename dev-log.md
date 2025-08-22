# Agent Arbitrage Development Log

### **Dev Log Entry: Debugging Session of Aug 18**

**Objective:** Resolve a recurring `SessionNotCreatedException` in the Selenium-based YouTube scraping function when running under Apache/mod_wsgi.

**Summary of Investigation:**
This was a complex and multi-layered bug. The initial error, `session not created: probably user data directory is already in use`, was misleading and masked several underlying issues related to the server environment, file permissions, application caching, and ultimately, a subtle race condition in the `webdriver-manager` library.

**Debugging Journey & Key Discoveries:**

1.  **Initial State & Misleading Paths:** The session began with the application failing to run correctly. Initial attempts to fix the Selenium error were hampered by an inability to reliably deploy code to the server. Methods such as direct file transfer via `message_user` and `base64` encoding repeatedly failed, pointing to a fundamental issue with the agent's tools or the communication channel.

2.  **The "Version Stamp" Breakthrough:** A key turning point was a user-suggested test: embedding a version number directly into the HTML template (`guided_learning.html`). This test definitively proved that new Python code *was* being executed by the server, debunking the theory that `mod_wsgi` was serving a cached file. This narrowed the problem down to the application logic itself.

3.  **Permissions & Syntax Errors:**
    *   A `Permission denied` error on `/var/www/agentarbitrage/.wdm/drivers.json` was solved by running `sudo chown -R www-data:www-data /var/www/agentarbitrage`, giving the web server user correct ownership of the application files.
    *   A `500 Internal Server Error` was traced back to a syntax error (an unquoted string for a file path) introduced during a manual edit. This highlighted the fragility of manual code transfer.

4.  **Final Diagnosis - The `webdriver-manager` Race Condition:** Even with permissions and syntax corrected, the `SessionNotCreatedException` returned, but only on the *second* and subsequent requests. The application logs confirmed that the `finally` block and `driver.quit()` were executing correctly. The final diagnosis is that the `ChromeDriverManager().install()` call, which runs on every request, is not thread-safe in a multi-threaded `mod_wsgi` environment. It was likely causing a race condition or file lock contention within the `.wdm` directory, leading to the crash.

**Final Proposed Solution (Not Yet Implemented):**

The most robust solution is to remove the `ChromeDriverManager().install()` call from the request cycle entirely. The correct approach for a server environment is to use a fixed, hard-coded path to the `chromedriver` executable.

**Action Plan for Next Session:**
1.  Start with a clean, stable codebase from the `main` branch.
2.  Create a new branch for the fix.
3.  Modify the `get_youtube_transcript_with_selenium` function in `wsgi_handler.py` to remove the `ChromeDriverManager` and replace it with a hard-coded path to the pre-downloaded `chromedriver` executable.
4.  Commit and submit this change via the `git` workflow to ensure a perfect, reliable file transfer.
5.  Guide the user through pulling and deploying this final, stable version.

**Session Conclusion:**
This debugging session, while long, was successful in identifying the true, low-level root cause of the bug. The application is now in a known-good (though still broken) state on the `main` branch, with a clear and actionable plan for the final fix.

---

## August 2025

This log provides a summary of the key development activities for the Agent Arbitrage project.

### **Week 1-2: Initial Setup and Guided Learning MVP (Early August)**

*   **Project Initialization:**
    *   Set up the Flask application structure on the Hostinger VPS.
    *   Established the initial technology stack: Python, Flask, `httpx`, `BeautifulSoup`.
    *   Configured the Apache server with WSGI to serve the Flask application.

*   **Guided Learning - Phase 1 (Scraping & Summarization):**
    *   Developed the `/guided_learning` page with a form for users to submit a URL or text.
    *   Implemented a scraping function in `app.py` to fetch and parse content from submitted URLs, stripping HTML tags to extract clean text.
    *   Integrated the Hugging Face API (`facebook/bart-large-cnn` model) to perform text summarization.

### **Week 2-3: Debugging and UX Improvements (Mid August)**

*   **Hugging Face API Authentication:**
    *   **Issue:** The application was failing to connect to the Hugging Face API, resulting in a `401 Unauthorized` error on the VPS.
    *   **Troubleshooting:** Discovered that the `.env` file containing the `HF_TOKEN` was not loading correctly in the Apache/mod_wsgi environment.
    *   **Resolution:** Modified `app.py` to use `load_dotenv('/var/www/agentarbitrage/.env')`, providing an explicit path to the `.env` file. Added logging to confirm the token was loaded successfully.

*   **Improving User Experience (UX):**
    *   **Issue:** The scraping and summarization process could take a significant amount of time, making the application feel unresponsive.
    *   **Resolution:**
        *   Added a progress spinner and a "Processing..." message to the `/guided_learning` page. The spinner appears after the user clicks "Submit for Analysis."
        *   Disabled the "Submit" and "Clear Session" buttons during processing to prevent multiple submissions.
        *   Improved the visual distinction between the "Submit" (blue) and "Clear Session" (red) buttons.

*   **Routing and Code Cleanup:**
    *   **Issue:** Redundant routing and authentication. The `/app` route was protected by Apache's Basic Authentication, creating a confusing double login.
    *   **Resolution:**
        *   Removed the `/app` route from `app.py` and the corresponding `<Location /app>` block from the Apache configuration.
        *   The root URL (`/`) now serves the login page (`index.html`), which submits to `/login` and redirects to `/guided_learning` on success.
        *   Updated `index.html` and `results.html` to use `url_for('guided_learning')` instead of the old `/app` route.

*   **Performance and Stability:**
    *   **Issue:** Summarization of very long texts was slow and sometimes failed.
    *   **Resolution:**
        *   Implemented a chunking mechanism in `app.py` to split long texts into smaller pieces (512 words) before sending them to the Hugging Face API.
        *   Limited the input text for summarization to 50,000 characters to prevent excessive processing times.
    *   **Issue:** Sensitive information (like `.env` files) could be accidentally committed.
    *   **Resolution:** Verified that the `.gitignore` file correctly excludes `.env`, `app.log`, and other sensitive files.

*   **Session Management:**
    *   **Issue:** Data persisted between sessions, causing confusion.
    *   **Resolution:** Improved the `/clear_session` route to properly clear all relevant data from the session and delete temporary files, providing a "Session cleared!" message to the user.

### **Next Steps (Week 2-3 Continued)**

*   **Extract Key Strategies:** Implement functionality to extract specific, actionable strategies and parameters (e.g., "sales rank between X and Y") from the summarized text.
*   **Approval Interface:** Display these extracted strategies on the `/results` page for user review, editing, and approval.



**Date: August 9, 2025**

- **Task:** Debug and resolve strategy extraction failure.
- **Issue:** The initial implementation using `mistralai/Mistral-7B-Instruct-v0.1` failed to extract strategies, returning an error.
- Troubleshooting:
  1. Enhanced error reporting in `app.py` to get detailed API responses.
  2. Added a retry mechanism to handle potential `503` errors caused by model loading times.
  3. The detailed error was a `404 Not Found`, indicating the Mistral model is not available on the standard Inference API.
  4. Upgraded to a Hugging Face Pro subscription to improve overall API stability and performance.
- **Resolution:** Decided to switch the strategy extraction model to `google/flan-t5-large`, which is a powerful and reliably available model for this task.

**Date: August 9, 2025**
- I have changed the strategy extraction model to t5-small in app.py.

**Date: August 12-15, 2025**

- **Task:** Debug persistent 404 errors for strategy extraction models and enhance strategy output.
- **Issue:** POST requests to `google/flan-t5-large`, `t5-small`, `bert-base-uncased`, `distilbert-base-uncased`, and `mistralai/Mixtral-8x7B-Instruct-v0.1` returned 404 ("Not Found", "X-Cache: Error from cloudfront") despite Pro account and correct headers/payloads.
- **Troubleshooting:**
  1. Tested models with curl (`facebook/bart-large-cnn` worked; others failed).
  2. Posted to Hugging Face General forum[](https://discuss.huggingface.co/c/general/10) and Discord #help, confirming non-`facebook/` models are not deployed on Inference API.
  3. Disabled leaked API key [REDACTED_HF_TOKEN_1] and generated new one [REDACTED_HF_TOKEN_1].
  4. Tested `mistralai/Mixtral-8x7B-Instruct-v0.1` (404, not deployed despite listing).
- **Resolution:** Reverted to `facebook/bart-large-cnn` for scraping and summarization. Optimized `app.py` prompt for actionable rules (e.g., sales rank, profit margin). Plan to test xAI API (free credit) for strategy extraction due to its reasoning capabilities.
- **Proposed Fix:** Update `app.py` to use `facebook/bart-large-cnn` for summarization, add xAI API fallback for strategy extraction, and refine regex for precise rules. Test 100-200 articles with xAI to align with project goal of failproof arbitrage.

#### 1. Task Complete: xAI API Integration

- **Objective**: To resolve persistent 404 errors from the Hugging Face Inference API for models critical to strategy extraction (e.g., `google/flan-t5-large`).

- Actions Taken

  :

  - The core issue was identified: the specified models were not deployed on the Hugging Face Inference API, meaning the issue was with the service, not our code.
  - The `app.py` logic was refactored to replace the failing Hugging Face model with the xAI API (`grok-4-latest` model), which is specifically designed for complex reasoning tasks.
  - A new `query_xai_api` function was created to handle authentication and requests to the new endpoint.
  - The `extract_strategies` function was updated to use the xAI API as its primary method, ensuring more precise and reliable rule extraction. The existing `facebook/bart-large-cnn` model was retained as a robust fallback.
  - Based on user feedback, the success message "Successfully extracted strategies using the xAI API." was updated to the more concise "Successfully extracted strategies."

- **Outcome**: The application is no longer subject to the Hugging Face API errors and can now reliably extract high-quality, actionable strategies from text.

#### 2. New Feature: YouTube Transcript Extraction

- **Objective**: To expand the application's data analysis capabilities to include spoken content from YouTube videos.

- Actions Taken

  :

  - The `youtube-transcript-api` library was identified as a lightweight and effective solution and was added to the project's dependencies.
  - The `learn` route in `app.py` was significantly enhanced. It now uses a regular expression to detect a wide range of YouTube URL formats.
  - If a YouTube URL is submitted, the application now bypasses the standard web scraper and instead calls the new library to fetch the video's full transcript.
  - The extracted transcript text is then seamlessly passed into the existing pipeline for summarization and strategy analysis.
  - The standard HTML scraping logic is preserved as the default behavior for all non-YouTube URLs.

- **Outcome**: This new feature dramatically increases the scope of content the application can analyze, unlocking a major source of valuable information for arbitrage strategies.


### Dev Log Entry: Debugging Session of Aug 17

**Objective:** Resolve a `SessionNotCreatedException` in a Flask application running under Apache/mod_wsgi.

**Initial Analysis:** The error (`user data directory is already in use`) suggested that multiple Selenium instances were conflicting. The initial fix attempt was to add the process ID (`os.getpid()`) to the `--user-data-dir` path in `app.py`.

**Debugging Journey:**

1. **Configuration Mismatch:** Initial efforts were hampered by a misconfiguration where Apache was pointing to an old `wsgi.py` instead of the updated `app.py`. This led to a series of debugging steps involving updating the `agentarbitrage.conf` file.

2. **500 Internal Server Error:** After correcting the config to point to `app.py`, the server began returning a 500 Internal Server Error. The Apache `error.log` was clean, and the application's own `app.log` showed that the new code was not being loaded, indicating a severe caching issue with `mod_wsgi`.

3. Forced Reload Attempts:

    

   Numerous strategies were employed to force

    

   ```
   mod_wsgi
   ```

    

   to reload the code, including:

   - Touching the script file.
   - Killing `mod_wsgi` and python processes.
   - Deleting `.pyc` cache files.
   - Renaming the main application file from `app.py` to `wsgi_handler.py` and updating the Apache config to match. None of these attempts resolved the issue.

4. **Permissions Issues:** An `ls -l` command revealed the newly-named `wsgi_handler.py` was owned by `root`, making it unreadable by the `www-data` user that Apache runs as. This was corrected with `chown`.

5. **Environment Issues:** After fixing permissions, the 500 error persisted. The `app.log` showed the new code was still not running. A hypothesis was formed that the app was crashing very early, before logging was configured, possibly due to a missing `.env` file. The Python code was rewritten to be more resilient and initialize logging first.

6. **"Hello World" Test:** With the 500 error still present and no useful logs, a minimal "Hello World" application was deployed in `test_app.py`. **This test was successful.** It proved conclusively that the server environment (Apache, `mod_wsgi`, Python venv, file permissions) is fundamentally working.

7. **Isolating the Fault:** The problem is definitively in the application code. An attempt was made to iteratively add code back to a minimal `wsgi_handler.py`. This was blocked by a recurring platform issue with the agent's `message_user` tool, preventing code from being communicated to the user.

**Current Status:** The application is broken. The server is configured to run a minimal, working version of `wsgi_handler.py`. The full application code causes a silent crash.

**Remaining Tasks:**

1. Systematically debug `wsgi_handler.py` to find the line(s) of code causing the crash.
2. Once the application is stable and running, fix the original `SessionNotCreatedException` from Selenium.

### **Dev Log Entry: Debugging Session of Aug 17**

**Objective:** Resolve a silent 500 Internal Server Error in a Flask application.

**Summary of Investigation:**

1. **Initial State:** Full application code in `wsgi_handler.py` caused a silent 500 Internal Server Error. No logs were generated in `app.log` or the main Apache `error.log`.
2. **Permissions & Working Directory:** It was discovered that the `mod_wsgi` process, running as `www-data`, did not have permission to write logs in the application directory. This was compounded by the fact that the process's working directory was `/` (the filesystem root). This was confirmed by instructing the user to run `chown` and by analyzing `agentarbitrage.conf`.
3. **Logging Breakthrough:** Analysis of `agentarbitrage.conf` revealed a custom log file: `/var/log/apache2/agentarbitrage_error.log`. This log contained the crucial error: `Target WSGI script ... does not contain WSGI application 'application'`.
4. **Environment Misunderstanding (Critical Failure):** The agent (Jules) was discovered to be working in an isolated sandbox, not directly on the user's server. This was a critical misunderstanding.
5. **Corrected Workflow:** A new workflow was established: the agent develops code and provides it to the user for deployment and testing.
6. **Tool Failure (Current Blocker):** The agent's tool for sending messages has been consistently truncating code, preventing the user from deploying a complete file. This is the direct cause of the current "404 Not Found" error.

**Next Steps (for New Task):**

1. Establish a reliable method to transmit the complete `wsgi_handler.py` file to the user.
2. Have the user deploy the complete file and restart the server.
3. Verify the full application loads.
4. Instruct the user to trigger the Selenium scraping function.
5. Analyze the resulting `app.log` traceback to diagnose and fix the original bug.

### Dev Log Entry: August 20, 2025 (Update 7)

**Objective**: Resolve 500 error and restore core functionality of Agent Arbitrage Flask application.

**Background**: The application was throwing a 500 error due to a misconfigured WSGI setup. Initial logs indicated that wsgi_handler.py did not contain a WSGI application callable, causing mod_wsgi to fail. Additionally, a prior rename of app.py to wsgi_handler.py (to bypass caching issues) and the presence of a wsgi.py file with invalid Apache directives complicated the setup. A syntax error in wsgi_handler.py’s get_youtube_transcript_with_selenium function further hindered progress.

**Struggles and Challenges**:

1. 500 Error Diagnosis

   :

   - Initial error: [Wed Aug 20 17:51:13.169498 2025] [wsgi:error] ... mod_wsgi (pid=122586): Target WSGI script '/var/www/agentarbitrage/wsgi_handler.py' does not contain WSGI application 'application'.
   - Confirmed wsgi_handler.py contained the full Flask app but lacked the application callable required by mod_wsgi.
   - Discovered wsgi.py existed, attempting to import app from a non-existent app.py, and included invalid Apache directives (LoadModule, WSGIPythonHome, WSGIPythonPath).

2. File Naming Confusion

   :

   - Previous rename of app.py to wsgi_handler.py was done to address caching issues, but it led to confusion about which file should serve as the WSGI entry point.
   - Considered reintroducing app.py but avoided it to prevent ripple effects (e.g., updating references in Apache config or other scripts).
   - Decided to keep wsgi_handler.py as the Flask app and use wsgi.py as the WSGI entry point to maintain existing structure.

3. Syntax Error in wsgi_handler.py

   :

   - The get_youtube_transcript_with_selenium function had a syntax error due to misplaced Bright Data proxy configuration code and a non-comment line (# new shit just added above - this one is not being read as a comment...).
   - The error caused the function to be incomplete, potentially contributing to runtime issues.

4. Apache Configuration Issues

   :

   - Apache config (agentarbitrage.conf) initially pointed to wsgi_handler.py instead of wsgi.py, causing the 500 error.
   - Missing LoadModule wsgi_module directive in agentarbitrage.conf, though mod_wsgi was already loaded (evidenced by AH01574: module wsgi_module is already loaded, skipping).
   - Invalid Apache directives in wsgi.py needed to be moved to agentarbitrage.conf.

5. Testing and Validation Challenges

   :

   - Multiple iterations of curl tests, log checks, and browser tests were required to confirm fixes.
   - Ensuring the virtual environment (venv) was correctly referenced in WSGIDaemonProcess (python-home=/var/www/agentarbitrage/venv).
   - Verifying SSL setup and redirects (http to https) in Apache config.

**Actions Taken**:

1. Fixed WSGI Setup

   :

   - Updated 

     wsgi.py

      to:

     python

     `import sys import os sys.path.insert(0, '/var/www/agentarbitrage') from wsgi_handler import app as application`

     This correctly imports the Flask app from 

     wsgi_handler.py

      and exposes the 

     application

      callable.

   - Removed invalid Apache directives from wsgi.py (LoadModule, WSGIPythonHome, WSGIPythonPath).

2. Corrected wsgi_handler.py Syntax

   :

   - Replaced the get_youtube_transcript_with_selenium function (from # new shit just added below to just before if __name__ == '__main__':) with a corrected version, consolidating proxy configuration and cleanup logic.
   - Preserved if __name__ == '__main__': app.run(debug=True) for local testing.

3. Updated Apache Config

   :

   - Modified 

     /etc/apache2/sites-available/agentarbitrage.conf

      to:

     - Ensure WSGIScriptAlias / /var/www/agentarbitrage/wsgi.py.
     - Add LoadModule wsgi_module /usr/lib/apache2/modules/mod_wsgi.so to guarantee mod_wsgi loading.
     - Retain existing WSGIDaemonProcess and WSGIProcessGroup for virtual environment and path setup.

   - Ran sudo apache2ctl configtest and sudo systemctl restart apache2 to apply changes.

4. Tested Application

   :

   - Ran curl -I https://localhost --insecure and curl https://localhost --insecure on the server, confirming HTTP 200 and homepage rendering.
   - Ran curl -I https://agentarbitrage.co --insecure and curl https://agentarbitrage.co --insecure from a Mac, confirming identical results.
   - Visited https://agentarbitrage.co in a browser, logged in with tester/OnceUponaBurgerTree-12monkeys, submitted https://youtu.be/YaF5JRqUm3c?si=8Qu5NVIz_3odJOSG, and reached /results.

5. Checked Logs

   :

   - Reviewed /var/log/apache2/agentarbitrage_error.log, /var/log/apache2/error.log, and /var/www/agentarbitrage/app.log.
   - Confirmed WSGI initialization and Python path setup in logs.
   - Identified new error in /results: Service /usr/local/bin/chromedriver unexpectedly exited. Status code was: 1.

**Current Status**:

- Homepage (https://agentarbitrage.co) is accessible, and login works, resolving the 500 error.
- Submission of a YouTube URL (https://youtu.be/YaF5JRqUm3c?si=8Qu5NVIz_3odJOSG) reaches /results, but transcript extraction fails due to a ChromeDriver error.
- Logs show successful API calls to Hugging Face and xAI, indicating summarization and strategy extraction are attempted, but the Selenium error prevents transcript retrieval.

**Next Steps**:

- Resolve ChromeDriver Error

  :

  - Investigate why /usr/local/bin/chromedriver exits with status code 1.
  - Verify ChromeDriver installation, version compatibility with Chrome, and permissions.
  - Check if Bright Data proxy credentials are configured (BRIGHTDATA_USERNAME, etc.) or if they’re needed to avoid YouTube blocks.

- Test Full Workflow

  :

  - Re-test YouTube URL submission after fixing ChromeDriver.
  - Confirm transcript extraction, summarization, and strategy extraction on /results.

- Evaluate Transcript Rules

  :

  - Once transcript extraction works, assess if extracted rules are actionable for book arbitrage.

- Check Bright Data Proxy

  :

  - Determine if proxy is required for reliable YouTube scraping.

- Update Repository

  :

  - Commit changes to wsgi.py, wsgi_handler.py, and agentarbitrage.conf.
  - Push to Git: git add wsgi.py wsgi_handler.py; git commit -m "Fixed WSGI setup and syntax error"; git push origin main.

**Lessons Learned**:

- Separating the Flask app (wsgi_handler.py) from the WSGI entry point (wsgi.py) is critical for mod_wsgi.
- Apache directives must reside in config files, not Python scripts.
- Syntax errors in critical functions (e.g., get_youtube_transcript_with_selenium) can be subtle and require careful validation.
- Comprehensive logging (app.log, Apache logs) is essential for debugging.
- Avoiding unnecessary file renames prevents configuration drift and reduces risk of breaking references.

**Timestamp**: August 20, 2025, 19:18 EDT

---

### Dev Log Entry: August 22, 2025 - Postponing YouTube Scraper Fix

**Objective:** Resolve the final errors in the YouTube transcript scraping functionality.

**Summary of Investigation:**
After resolving authentication and proxy configuration issues, the application was successfully refactored to use the `youtube-transcript-api` library. However, a persistent `AttributeError` (`'YouTubeTranscriptApi' object has no attribute 'list_transcripts'`) blocked progress.

**Debugging Journey:**
1.  **Initial `AttributeError`:** The first error indicated that `get_transcript` was not a valid method. The code was refactored to use the documented `list_transcripts` method.
2.  **Second `AttributeError`:** The error persisted, but changed to indicate `list_transcripts` was also not a valid method. This led to the discovery that the API class needed to be instantiated first (`api = YouTubeTranscriptApi()`).
3.  **Third `AttributeError`:** A final error (`'YouTubeTranscriptApi' object has no attribute 'list_transcripts'`) occurred after the instantiation fix. This was traced to a typo in the method name (`list_transcripts` instead of the correct `list`).
4.  **Final State & Discrepancy:** A final version of the code, correcting the method to `api.list()`, was provided to the user. However, the user reported that this correct code was already on their server, yet the error persisted. A significant and unresolved discrepancy exists between the code I am able to read from the environment and the code the user reports is running on the server.

**Decision:**
Due to the persistent and unresolvable nature of this bug, and the risk of spending more time without progress, the user has made the decision to **postpone this feature**. The current (non-functional) YouTube transcript code will remain, but we will move on to other development tasks to keep the project on track.

**Action Plan:**
1.  Document this issue in `dev-log.md`.
2.  Add a "Postponed Tasks" section to the main project plan to ensure this is not forgotten.
3.  Proceed with the next development task as defined by the user.

---

### Dev Log Entry: August 22, 2025 - UX, Navigation, and Strategy Persistence

**Objective:** Transition the application from a set of disconnected tools into a more cohesive web application by implementing core UX features and the ability to save and view approved strategies.

**Summary of Features and Fixes:**

1.  **Admin Navigation and Layout:**
    *   **New Base Template:** Created a `templates/layout.html` file to serve as a consistent base for all admin-facing pages.
    *   **Persistent Navigation:** Added a navigation bar to the layout with links to "Guided Learning," "Strategies," and "Logout."
    *   **Template Refactoring:** Updated `guided_learning.html` and `results.html` to extend the new base layout, unifying the application's look and feel.
    *   **Logout Functionality:** Implemented a `/logout` route that successfully clears the user's session and redirects to the login page.

2.  **User Experience (UX) Improvements:**
    *   **"Enter-to-Submit":** Added a JavaScript listener to the Guided Learning page so that pressing "Enter" in the textarea submits the form for analysis.
    *   **Results Page Layout:** Adjusted the CSS in `static/global.css` to improve the layout of the results page. The non-editable "Original Input" and "Scraped Text" boxes are now fixed-height with scrollbars, while the editable "Summary" and "Strategies" textareas have a larger default size for easier editing.
    *   **API Timeout:** Increased the timeout for the xAI API call from 30 to 90 seconds to handle longer processing times for strategy extraction from large texts.
    *   **AI Fallback Behavior:** Modified the prompt sent to the xAI model to prevent it from providing generic, non-contextual advice when it cannot find relevant strategies in the provided text.

3.  **Strategy Persistence:**
    *   **Saving Strategies:** Implemented logic in the `/approve` route to save the content of the "Extracted Strategies" textarea. The strategies are treated as a newline-separated list, deduplicated against existing strategies, and saved to `strategies.json`.
    *   **Displaying Strategies:** The `/strategies` route now reads the `strategies.json` file and passes the list of saved strategies to the `strategies.html` template for display.
    *   **Bug Fixes:**
        *   Resolved a `PermissionError` by changing the `strategies.json` file path from relative to absolute, ensuring the web server process always writes to the correct directory.
        *   Diagnosed and fixed a display issue on the strategies page by changing the rendering from an `<ol>` to a series of `<p>` tags.

**Current Status:**
The core admin workflow is now significantly improved. An admin can log in, submit text for analysis, approve the results, have those results saved permanently, and view the collection of all saved results. The application has a consistent navigation structure and a more polished user experience.
