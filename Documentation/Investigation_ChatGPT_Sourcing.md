# Investigation Report: ChatGPT Instant Checkout for Sourcing

**Date:** 2026-01-XX
**Topic:** Investigating "ChatGPT Instant Checkout" to source books at the lowest cost from all possible sellers.

## Executive Summary

**The specific tool "ChatGPT Instant Checkout" cannot be used for this purpose.**

"Instant Checkout" is a feature designed for **merchants** to sell products *to* ChatGPT users via the "Agentic Commerce Protocol" (ACP). It is not a tool for developers to **source** or query prices from a wide range of sellers. OpenAI does not expose a public "Shopping Search API" that would allow us to programmatically search their merchant index.

However, the goal of "sourcing the cheapest book from all possible sources" (eBay, AbeBooks, ThriftBooks, Google Shopping) is **highly feasible** using alternative, standard technologies.

## Detailed Analysis

### 1. What "Instant Checkout" Actually Is
*   **For Merchants:** It allows a store (like a Shopify or Etsy seller) to expose their catalog to ChatGPT so users can say "Buy this" directly in the chat.
*   **For Users:** It provides a "Buy" button inside the ChatGPT interface.
*   **Limitation:** There is no public API that allows a third-party application (like ours) to send a query like *"Find the best price for ASIN X from all Instant Checkout merchants"* and get a structured list of prices back. The discovery process is controlled entirely by OpenAI's internal search algorithms within their consumer chat product.

### 2. Why It Doesn't Work "Behind the Scenes"
To use ChatGPT for sourcing "behind the scenes," we would essentially need to build a bot that acts like a human user:
*   It would have to open a chat session.
*   Ask: *"Find me the cheapest copy of 'Harry Potter' from all your merchants."*
*   Parse the natural language response.
*   **Risks:** This approach (scraping/automating the chat client) is slow, expensive, prone to breaking when OpenAI changes their UI/models, and likely violates Terms of Service. It is not a stable foundation for a business-critical pricing engine.

## Recommended Solution: Multi-Vendor Sourcing API

To achieve the user's goal of "Best Price from All Sources," we should integrate dedicated sourcing APIs rather than trying to reverse-engineer a consumer chat feature.

**Suggested Data Sources:**
1.  **Google Shopping API (via SerpApi or DataForSEO):**
    *   **Pros:** Aggregates results from eBay, ThriftBooks, AbeBooks, Walmart, and smaller stores.
    *   **Cost:** Low (per search).
    *   **Data:** Returns price, shipping cost, seller name, and direct link.
2.  **eBay Finding API:**
    *   **Pros:** Direct access to the largest secondary market for books.
    *   **Cost:** Free (up to limits).

### Integration Roadmap

Even without ChatGPT, we can implement "Buy from All Sellers". Here is the technical roadmap for modifying the current architecture:

#### A. Data Model Updates
We need to store the "External Source" data alongside the Keepa (Amazon) data.
*   **New Columns:** `External_Price`, `External_Shipping`, `External_Seller`, `External_Link`, `External_Platform` (e.g., 'eBay').

#### B. Logic Updates (`keepa_deals/processing.py`)

Currently, `_process_single_deal` calls `seller_info.get_used_product_info` which only looks at Amazon. We would inject a new step:

```python
# Pseudo-code for future implementation
def _process_single_deal(product_data, ...):
    # 1. Existing Amazon Logic
    amazon_price, amazon_seller, ... = get_used_product_info(product_data)

    # 2. NEW: External Sourcing (e.g., Google Shopping)
    external_deal = external_sourcing_service.find_best_price(asin)

    # 3. Compare and Pick Winner
    if external_deal and external_deal['total_price'] < amazon_price:
        row_data['Price Now'] = external_deal['total_price']
        row_data['Best Price'] = external_deal['total_price']
        row_data['Seller'] = f"{external_deal['platform']} - {external_deal['seller']}"
        row_data['Buy Now URL'] = external_deal['link']
        row_data['Is_External'] = True
    else:
        # Keep existing Amazon data
        ...
```

#### C. Profit Calculation Updates (`keepa_deals/business_calculations.py`)

The `calculate_all_in_cost` function needs to handle external purchases where Amazon fees might not apply *at the point of purchase*, but still apply *at the point of sale* (if doing Arbitrage).

*   **Acquisition Cost:** The `Price Now` would be the external price (e.g., eBay price + shipping).
*   **Fees:**
    *   If **Online Arbitrage (OA):** We buy on eBay (Pay eBay Price + Ship) -> Send to Amazon (Pay Inbound Ship) -> Sell on Amazon (Pay Referral + FBA).
    *   **Logic Change:** The calculation remains largely the same (`Price Now` is your Cost of Goods), but we might need to adjust `estimated_shipping` if the external source charges specific shipping that we already captured in `Price Now`.

## Conclusion

**Do not use ChatGPT Instant Checkout.** It is a dead end for this specific use case.

**Do use a Shopping Aggregator API.** This will provide the "Best Price from Anywhere" feature reliably and can be integrated directly into the current `processing.py` pipeline with minimal friction.
