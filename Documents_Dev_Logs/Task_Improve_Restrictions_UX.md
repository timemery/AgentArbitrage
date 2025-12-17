# Task: Investigate Amazon "Apply to Sell" Links & Production Data Mismatch

**Context:**
The previous agent successfully enabled the "Check Restrictions" feature by resolving authentication issues (removed SigV4, fixed 403 by switching to Sandbox endpoint). However, the user reports two remaining issues affecting the usability of this feature:

1.  **Broken "Apply" Links:** The generated approval URLs (e.g., `https://sellercentral.amazon.com/product-search/search?q=B0006BMZFQ`) redirect to a generic Seller Central search page instead of the specific "Apply to Sell" workflow for that ASIN. This forces the user to manually search for the product again.
2.  **100% Restriction Rate (Data Mismatch):** Every item is showing as "Restricted" ("Apply"). The user is an established seller (4 years) and finds it unlikely they are restricted on all books.
    *   **Hypothesis:** The app is currently using the **SP-API Sandbox Endpoint**. The Sandbox often lacks real-world account data and might return a default "Restricted" status for real ASINs that aren't part of its static test set. To see accurate data reflecting the user's history, the app likely needs to connect to the **Production Endpoint**.

**Objectives:**

1.  **Fix "Apply to Sell" Deep Links:**
    *   Investigate why the current constructed URL format fails (redirects to generic search).
    *   Reverse engineer or research the correct Seller Central deep link format for applying to sell a specific ASIN (e.g., `https://sellercentral.amazon.com/hz/approvalrequest?asin=...` or similar).
    *   Update `keepa_deals/amazon_sp_api.py` to generate functional links.

2.  **Transition to Production SP-API:**
    *   **Goal:** Connect the Private App to the Production Endpoint to retrieve real account eligibility data.
    *   **Current State:** The user's current token works on Sandbox (`200 OK`) but fails on Production (`403 Forbidden`).
    *   **Investigation:**
        *   Why is the current token Sandbox-only? (Was it generated via a Sandbox-specific flow? Is the App in a "Draft" state that restricts Production access?)
        *   **Note:** Private Apps *can* access Production data without being Public or incurring fees.
    *   **Action:**
        *   Guide the user to generate a **Production-valid** Refresh Token. This usually involves authorizing the app in Seller Central without checking "Sandbox" options, or ensuring the IAM/App configuration allows Production access.
        *   Once a valid token is obtained, update the `SP_API_URL` environment variable to point to `https://sellingpartnerapi-na.amazon.com`.

**Reference Files:**
*   `keepa_deals/amazon_sp_api.py`: Contains the `check_restrictions` logic and URL construction.
*   `Diagnostics/diag_test_sp_api.py`: Use this to test if a new token works on Production (`mp_url`).

**Success Criteria:**
*   "Apply" buttons link directly to the approval page for the ASIN.
*   The "Gated" status accurately reflects the user's selling history (i.e., fewer restrictions).
