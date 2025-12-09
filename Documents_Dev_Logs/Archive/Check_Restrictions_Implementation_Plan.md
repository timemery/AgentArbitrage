# Development Plan: Check Restrictions Feature

This document outlines the research and development plan for implementing a feature that allows users to check if they are restricted from selling a book on Amazon.

## 1. Feature Overview

The goal is to provide a clear, low-friction way for users to see if they are "gated" for a specific ASIN and to easily apply for approval if needed. The feature will integrate with the Amazon Selling Partner API (SP-API) and display the restriction status directly on the deals dashboard. To prevent UI lag and handle API rate limits, the checks will be performed asynchronously in the background.

## 2. Technical Approach & Architecture

### Key Technologies
- **Amazon Selling Partner API (SP-API):** The official Amazon API for accessing seller account data.
  - **Authentication:** OAuth 2.0 "Website authorization workflow".
  - **Endpoint:** `listings/2021-08-01/restrictions` will be used to check the gating status for a given ASIN. This endpoint has a rate limit of approximately 1 request per second.
- **Celery:** The existing background task processing framework will be used to perform the API calls asynchronously, preventing the main web application from blocking.

### High-Level Workflow
1.  A user connects their Amazon Seller Central account to the application via a one-time OAuth 2.0 process.
2.  Once authorized, a Celery background task is triggered to check the restriction status for all existing ASINs in the `deals` database for that specific user.
3.  The results are stored in a new, separate database table (`user_restrictions`).
4.  The dashboard UI joins the deal data with the user-specific restriction data to display the status.
5.  The UI is designed to handle three states: `restricted`, `not_restricted`, and `pending_check`, ensuring a responsive user experience while the background task is running.
6.  As new deals are added to the system, targeted background tasks will check their restriction status for all connected users.

---

## 3. Detailed Implementation Plan

### Step 1: User Authorization and Configuration
- **UI:** Add a new section to the `/settings` page for "Amazon SP-API Integration".
- **Button:** This section will feature a button labeled "Connect Your Amazon Account".
- **OAuth Flow:** Clicking this button will redirect the user to the Amazon Seller Central login and consent page. This is the start of the standard SP-API "Website authorization workflow".
- **Callback Route:** Create a new Flask route (e.g., `/amazon_callback`) to handle the redirect from Amazon after the user grants consent.
- **Token Storage:** This callback route will be responsible for receiving the authorization token from Amazon and storing it securely, associated with the user's account.
- **UI Feedback:** The settings page should display the connection status (e.g., "Connected as [Seller Name]" or "Not Connected").

### Step 2: Create a New Database Table for Restriction Data
- **Table Name:** `user_restrictions`.
- **Purpose:** To store user-specific gating information, keeping it separate from the global `deals` data.
- **Schema:**
  - `id`: Primary Key
  - `user_id`: Foreign Key to the user's table.
  - `asin`: The ASIN of the product.
  - `is_restricted`: Boolean value indicating the gating status.
  - `approval_url`: A string to store the direct link for applying for approval (if provided by the API).
  - `last_checked_timestamp`: A timestamp to track when the status was last updated.

### Step 3: Asynchronous Background Processing for Restriction Checks
- **New Module:** Create a dedicated module, `amazon_sp_api.py`, to encapsulate all logic for interacting with the SP-API.
- **Main Celery Task:** Create a new Celery task `check_all_restrictions_for_user(user_id)`.
  - **Trigger:** This task will be triggered *once* immediately after a user successfully completes the OAuth flow.
  - **Logic:**
    1.  Fetch all unique ASINs from the `deals` table.
    2.  Iterate through the list of ASINs.
    3.  For each ASIN, call the SP-API `listings/2021-08-01/restrictions` endpoint, respecting the 1 request/second rate limit.
    4.  Save the result (restricted status and approval URL) into the `user_restrictions` table for the corresponding `user_id` and `asin`.
- **Incremental Update Task:** Modify the existing data-sourcing tasks (`update_recent_deals`, `backfill_deals`).
  - **Trigger:** When these tasks add a *new* ASIN to the `deals` table.
  - **Logic:** For each new ASIN, trigger a smaller, targeted background task that checks its restriction status for all users who have connected their SP-API accounts.

### Step 4: Integration with the Deals Dashboard
- **Backend API (`/api/deals`):**
  - Modify the query in the `api_deals` function in `wsgi_handler.py`.
  - For an authenticated user with a connected SP-API account, perform a `LEFT JOIN` from the `deals` table to the `user_restrictions` table on the `asin` column where `user_restrictions.user_id` matches the current user.
  - The API response for each deal should include a new field, `restriction_status`, which can have one of three values: `restricted`, `not_restricted`, or `pending_check` (if the JOIN results in a NULL record from `user_restrictions`).
- **Data Payload:** Also include the `approval_url` in the API response if available.

### Step 5: Frontend UI Enhancements for Asynchronous Loading
- **JavaScript Logic:** Update the dashboard's JavaScript to correctly interpret the new `restriction_status` field for each deal.
- **"Gated" Column Display Logic:**
  - If `restriction_status` is `pending_check`, display a loading icon/spinner. This provides immediate user feedback.
  - If `restriction_status` is `not_restricted`, display a green checkmark icon.
  - If `restriction_status` is `restricted`:
    - Display an "Apply for Approval" link/button that opens the `approval_url` in a new tab.
    - Apply a distinct CSS class (e.g., `gated-row`) to the entire table row to highlight it.

---

## 4. Summary of Deliverable

The final deliverable of this research and planning task is this document, which provides a comprehensive and actionable plan for a future development task. No code implementation is required for the current task.