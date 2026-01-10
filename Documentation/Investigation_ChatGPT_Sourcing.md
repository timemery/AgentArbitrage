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

To achieve the user's goal of "Best Price from All Sellers", we should integrate dedicated sourcing APIs rather than trying to reverse-engineer a consumer chat feature.

**Suggested Data Sources:**
1.  **Google Shopping Search (via Aggregators):**
    *   **Direct API:** Google does *not* offer a free public API for searching Shopping results.
    *   **Via SerpApi:** Approx. **$0.60 per 1,000 searches** (Paid).
    *   **Via DataForSEO:** Approx. **$0.50 - $2.00 per 1,000 searches** (Paid).
    *   **Pros:** Aggregates results from eBay, ThriftBooks, AbeBooks, Walmart, and smaller stores.
    *   **Cons:** Paid service; adds recurrent operational costs.

2.  **eBay Finding / Browse API:**
    *   **Cost:** **Free** (up to 5,000 calls/day for basic tier).
    *   **Pros:** Direct access to the largest secondary market for books.
    *   **Cons:** Only covers eBay; variable shipping costs.

### Cost & Risk Analysis

The user specifically asked about the "Free" nature of these APIs and the potential risks.

#### 1. Cost Realities
*   **Google Shopping is NOT Free:** To search Google Shopping programmatically, you must use a third-party SERP provider (like SerpApi).
    *   **Scale Cost:** If we backfill 10,000 deals, that is ~10,000 API calls. At $0.60/1k, that is ~$6.00 per full scan. While "low", it is not zero.
    *   **Rate Limits:** Free tiers on these SERP providers are usually very small (e.g., 100 searches/month), making them unsuitable for production backfills without a paid plan.
*   **eBay API:** Truly free for moderate volume (5,000 calls/day), but requires a Developer Account and strict adherence to their quota policies.

#### 2. Implementation Risks & Complexity
Adding multi-vendor sourcing introduces significant complexity ("Large" T-Shirt Size task).

*   **Risk A: Data Matching (The "False Positive" Trap)**
    *   **Problem:** Searching "Harry Potter" on eBay might return a different edition, a heavily damaged copy, or a "Study Guide" instead of the book.
    *   **Mitigation:** Must strictly match by **ISBN/EAN**. Title matching is dangerous for arbitrage.
*   **Risk B: Shipping Cost Variability**
    *   **Problem:** Amazon prices often include Prime (Free Shipping). eBay/AbeBooks often have "$5.00 + $3.99 Shipping".
    *   **Impact:** If we ignore shipping, we will calculate false profits. We must parse and add shipping costs for every external offer.
*   **Risk C: Latency & Backfill Speed**
    *   **Problem:** Currently, the Backfiller is limited by Keepa's tokens. Adding a synchronous call to eBay/Google for *every* item will drastically slow down the pipeline.
    *   **Impact:** A backfill that takes 2 hours could take 10+ hours if we wait 1-2 seconds for an external API response per item.
    *   **Mitigation:** Asynchronous fetching or "On-Demand" fetching (only check external prices when a user clicks a deal).

### Integration Roadmap

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

    # 2. NEW: External Sourcing (e.g., eBay API)
    # WARNING: This adds latency. Consider doing this only for high-margin potentials.
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

**Proceed with Caution on Multi-Vendor Sourcing.** While technically feasible via eBay API (Free) or SerpApi (Paid), it significantly increases system complexity and latency.
*   **Recommendation:** Start with a "Pilot" integration of the **eBay Finding API** (due to zero cost) on a "Check Price" button click, rather than integrating it into the main Backfill loop. This minimizes risk and latency.
