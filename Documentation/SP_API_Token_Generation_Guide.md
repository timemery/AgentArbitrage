# How to Generate a New SP-API Refresh Token

This guide is for **Private Apps** (Self-Authorization) to fix missing permissions (e.g., Inventory Tracking).

### Step 1: Login to Seller Central
Go to [Seller Central > Apps & Services > Develop Apps](https://sellercentral.amazon.com/selling-partner/app-list).

### Step 2: Edit Your App Permissions
1.  Find your app: `AgentArbitrage-Prod` (or similar).
2.  Click the arrow next to "Edit App" and select **Edit App**.
3.  Ensure the following Roles are checked:
    *   **Inventory and Order Tracking** (Required for Sync)
    *   **Pricing**
    *   **Product Listing**
4.  Click **Save and Exit**.

### Step 3: Re-Authorize (Generate New Token)
1.  On the "Develop Apps" page, find your app again.
2.  Click the arrow next to "Edit App" and select **Authorize**.
3.  Click **Authorize App**.
4.  A new **Refresh Token** (starting with `Atzr|...`) will be displayed.
5.  **Copy this token immediately.** You cannot view it again later.

### Step 4: Update Agent Arbitrage
1.  Go to **Settings** in Agent Arbitrage.
2.  Find the **"Manual Credentials Update"** section.
3.  Click **Toggle Manual Update Form**.
4.  Paste your **Seller ID** and the **New Refresh Token**.
5.  Click **Update Credentials**.
6.  Go to the **Tracking** page and click **Sync from Amazon**.

---
**Troubleshooting:**
*   If you still see "No active inventory found", wait 15 minutes. Amazon sometimes delays permission updates.
*   Ensure your Seller Central account has active listings.
