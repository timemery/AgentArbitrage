# Amazon SP-API Upgrade Guide

To enable **Profit & Inventory Tracking**, your Amazon SP-API Application requires additional permissions (Roles) beyond the basic restriction checks.

## Step 1: Update Your App in Seller Central

1.  Log in to [Amazon Seller Central](https://sellercentral.amazon.com/).
2.  Navigate to **Menu** > **Partner Network** > **Develop Apps**.
3.  Find your application ("Agent Arbitrage") in the list.
4.  Click the arrow next to "Edit App" and select **Edit App**.
5.  Under **LWA Credentials**, ensure your Client ID matches what is in your `.env` file. (Do not change this unless necessary).
6.  Scroll down to **Roles**. You must check/enable the following:
    *   **Product Listing** (Required for product info)
    *   **Pricing** (Required for competitive pricing data)
    *   **Inventory and Order Tracking** (CRITICAL: Required for `GET_MERCHANT_LISTINGS_ALL_DATA` report)
    *   **Amazon Fulfillment** (Optional, recommended for FBA data)
7.  Click **Save and Exit**.

*Note: If your app is in "Draft" status, these changes are immediate. If it is published, it may require re-review, but for private/draft apps used for self-authorization, it is instant.*

## Step 2: Re-Authorize in Agent Arbitrage

Adding roles does not automatically update your existing access tokens. You must re-run the connection flow.

1.  Go to your **Agent Arbitrage Dashboard**.
2.  Navigate to **Settings**.
3.  Click the yellow **"Connect Amazon"** button.
4.  You will be redirected to Amazon.
5.  **Crucial:** You should see a consent screen asking to authorize access to the *new* data categories (Inventory, Orders, etc.).
6.  Confirm the authorization.
7.  You will be redirected back to Agent Arbitrage with a success message.

## Step 3: Verify

1.  Go to the **Tracking** page.
2.  Click **"Sync from Amazon"**.
3.  If the permissions are correct, the sync will start without a "403 Forbidden" error in the logs.
