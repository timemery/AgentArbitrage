# Task: Investigate Amazon "Apply to Sell" Links & Production Data Mismatch

**Context:**
The previous agent successfully enabled the "Check Restrictions" feature by resolving authentication issues (removed SigV4, fixed 403 by switching to Sandbox endpoint). However, the user reports two remaining issues affecting the usability of this feature:

1.  **Broken "Apply" Links:** The generated approval URLs (e.g., `https://sellercentral.amazon.com/product-search/search?q=B0006BMZFQ`) redirect to a generic Seller Central search page instead of the specific "Apply to Sell" workflow for that ASIN. This forces the user to manually search for the product again.
2.  **100% Restriction Rate (Data Mismatch):** Every item is showing as "Restricted" ("Apply"). The user is an established seller (4 years) and should not be restricted on all books. This is highly likely because the app is currently configured to use the **SP-API Sandbox Endpoint**, which returns mock/fake data (often defaulting to "Restricted" for everything). To see real data reflecting the user's actual account history, the app must connect to the **Production Endpoint**.

**Objectives:**

1.  **Fix "Apply to Sell" Deep Links:**
    *   Investigate why the current constructed URL format fails.
    *   Reverse engineer or research the correct Seller Central deep link format for applying to sell a specific ASIN (e.g., `https://sellercentral.amazon.com/hz/approvalrequest?asin=...` or similar).
    *   Update `keepa_deals/amazon_sp_api.py` to generate functional links.

2.  **Transition to Production SP-API:**
    *   Verify if the user's credentials can access the Production endpoint (`https://sellingpartnerapi-na.amazon.com`).
    *   The previous diagnosis showed a 403 Forbidden on Production but 200 OK on Sandbox. This suggests the LWA token or App configuration is currently Sandbox-only.
    *   **Action:** Guide the user or investigate how to get a *Production-valid* LWA token. This might involve:
        *   User changing settings in Seller Central (moving app from "Draft" to "Published" or authorizing differently).
        *   User updating `.env` with Production credentials if they differ.
    *   Once a valid Production token is available, update the configuration (via `SP_API_URL` env var or code default) to point to Production.

**Reference Files:**
*   `keepa_deals/amazon_sp_api.py`: Contains the `check_restrictions` logic and the URL construction.
*   `Diagnostics/diag_test_sp_api.py`: A useful script to test tokens against both Sandbox and Production endpoints.

**Success Criteria:**
*   "Apply" buttons in the dashboard take the user directly to a page where they can request approval for the specific item.
*   The "Gated" status reflects the user's *actual* selling eligibility (i.e., not 100% restricted for an established seller).
