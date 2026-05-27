# Agent Arbitrage: Product Overview

**Version 3.5 — May 2026**
**Distribution:** Confidential. For NDA-protected partners, investors, and key stakeholders.

---

## What It Is

Agent Arbitrage is an AI-powered deal intelligence and operations platform for Amazon FBA booksellers — purpose-built for the niche of online sourcing and selling of used textbooks and scholarly non-fiction. It continuously monitors the Amazon marketplace, identifies books trading meaningfully below their historical clearing price, calculates true net profit after every real cost, and surfaces only the deals worth acting on. It then carries those deals through purchase, inventory, and realized sale in a single connected workflow.

The platform sits at the intersection of market data analytics, applied AI reasoning, and operational workflow tooling. It replaces hours of manual research and a patchwork of spreadsheets with a self-maintaining pipeline that delivers curated, profit-validated opportunities and tracks them all the way to settled revenue.

---

## The Problem It Solves

Used book arbitrage on Amazon is a proven business model with a real bottleneck: identifying genuinely profitable inventory at scale. Doing it right requires cross-referencing sales history, pricing trends, seasonal demand, seller competition, Amazon's own pricing behavior, gating restrictions, and the seller's personal cost structure — across thousands of products simultaneously, in real time.

The existing tool ecosystem forces sellers into a fragmented workflow:

1. A **sourcing tool** (Keepa, ScoutIQ, Tactical Arbitrage, SellerAmp, BookMine) to find candidate products.
2. A **spreadsheet** to track what they bought, what they paid, and what's at Amazon.
3. **Seller Central tabs** to reconcile real fees, gating status, and inventory counts.
4. An **inventory accounting tool** (InventoryLab or Sellerboard) to estimate profit — with reconciliation gaps because Amazon's deferred fee posting causes recurring discrepancies.

The result is that most sellers either under-invest in research and miss deals, or rely on tools that show raw data without context and make bad buys. The cottage industry of paid Excel templates (Caleb Roth's Book Flipper spreadsheet has 155 ratings; Gumroad sellers charge $14–$50 for FBA tracking templates) is direct evidence the gap is real and unsolved.

Agent Arbitrage closes the loop. Deal discovery, AI judgment, gating verification, purchase tracking, inventory state, and realized profit are one system.

---

## Strategic Differentiators

These are the capabilities that distinguish Agent Arbitrage from every comparable tool in the category. They are summarized here and detailed in the sections that follow.

1. **Curated deals only.** The dashboard never shows raw data. Every surfaced deal has passed multi-stage validation including AI reasonableness, true-cost math, and a hard pricing safety ceiling. Competitors show everything and ask the user to sort the signal from the noise.

2. **Inferred Market Clearing Price.** Three years of historical Amazon data are reconstructed into verified transaction prices — what the market actually paid, not what sellers were asking. All profit projections are built on this foundation. No competitor builds pricing on inferred-sale logic at this fidelity.

3. **Continuously sharpened AI judgment.** The platform's AI is informed by a constantly maintained knowledge base of arbitrage strategies and market intelligence specific to the online book arbitrage niche. This knowledge is curated by the operator (not crowd-sourced or static), distilled from expert sources, and regularly homogenized to stay concise and current. The result is an AI advisor that evaluates deals against rules and frameworks specifically tuned to used-book arbitrage, not generic e-commerce heuristics. *See "How the AI Gets Smarter" below.*

4. **AI reasonableness validation on every recommended price.** Each pricing recommendation is reviewed by a reasoning model that checks the projected price against the book's metadata (title, category, binding, page count, sales rank). Prices above $1,500 are rejected outright. Prices more than 3× current market trigger mandatory scrutiny. No competitor we audited applies AI validation as a gate on its own pricing math.

5. **End-to-end workflow in one tool.** Sourcing, gating verification, purchase tracking, FBA inventory state, and FIFO-matched realized profit live in one platform. No competitor — including category leaders InventoryLab and Sellerboard — covers this full loop natively.

6. **Built for work-from-anywhere sellers.** The entire platform runs in the browser. There is no scanner, no warehouse software, no on-premise dependency. Sellers operating against the US Amazon marketplace through a US-based prep warehouse — including international operators selling into the US from Canada, the UK, Australia, and elsewhere — can run their entire sourcing and inventory operation from any laptop, anywhere. The niche of "used textbooks and scholarly non-fiction sold online into US Amazon FBA via a prep partner" is exactly the operation this platform was designed for.

---

## Core Capabilities

### 1. Continuous Deal Discovery

The platform runs a background data engine — the Smart Ingestor — that queries the definitive Amazon pricing history database on a continuous, minute-by-minute basis. It scans for books whose current used price has dropped meaningfully below their established historical average.

This is not a simple price comparison. The pipeline distinguishes between:

- Books that sell reliably vs. those with inflated or stale list prices
- Active deals with real buyer demand vs. dead inventory sitting unsold
- Genuine price dips vs. pricing errors and seller-side repricer mistakes

Every candidate book passes through a multi-stage validation pipeline before reaching the user. Books that fail validation are retained in the background database for future re-evaluation but never surfaced — keeping the dashboard a high-signal feed instead of a firehose.

### 2. Inferred Market Clearing Price (The Core Innovation)

The platform's pricing logic is built on a proprietary concept: **inferred sales**. Rather than relying on list prices or asking-price averages (which can be inflated, stale, or manipulated), the system reconstructs actual historical transactions by correlating two independent data signals:

- A drop in offer count — indicating a unit was purchased
- A corresponding drop in sales rank — confirming Amazon registered the transaction

When both signals occur within a 10-day window, a sale is confirmed. The price at that moment is recorded as a verified transaction price. **All profit calculations are derived exclusively from these verified prices.**

This methodology was refined through extensive real-world testing. A fallback approach that estimated prices using listing averages — briefly tried as a stopgap — was permanently removed in March 2026 after it consistently produced inflated profit projections. The system now holds a firm line: if it cannot confirm a true sale, it will not project profit.

For books where the standard detection method finds no sales (e.g., sellers with deep inventory whose offer count doesn't drop with each sale), an AI-powered rescue mechanism analyzes historical rank and price data to identify "hidden sales" — rank improvements that signal a purchase even without an observable offer-count change.

The competitive significance: every other tool in the category derives prices from listing averages, Keepa's published statistics, or seller-reported sale data. None reconstruct verified historical transactions at this granularity. This is the technical foundation that makes "curated deals only" possible.

### 3. AI-Validated Pricing & Profit Calculation

Every deal's recommended listing price passes through a multi-layer validation pipeline before reaching the user:

**Peak Season Pricing.** The system identifies each book's historical peak selling season and calculates the mode price during that period — the price most frequently achieved at peak, not a mathematical average. For textbooks, this correctly captures semester-driven price spikes that can be 200–400% above off-peak pricing.

**Amazon Price Ceiling.** The recommended listing price is automatically capped at 90% of Amazon's own new price across current, 6-month, and 12-month averages. Every deal remains competitive against Amazon's direct sales.

**AI Reasonableness Check.** Each pricing recommendation is validated by an AI reasoning model, which reviews the book's title, category, binding, page count, image, and sales rank to determine whether the projected price is credible. Prices above $1,500 are rejected automatically. Prices more than 3× the current used price trigger mandatory scrutiny regardless of source.

**Business Math.** The platform calculates all-in acquisition cost (purchase price, sales tax, prep fee, shipping to Amazon), net profit after Amazon's FBA and referral fees, margin percentage, ROI, and minimum viable listing price — personalized to each user's cost structure entered in their settings.

### 4. Seasonality Intelligence

Amazon book sales are highly seasonal. Textbooks spike at semester start. Test prep materials surge before exam dates. Reference and professional books follow certification calendars. The platform uses AI classification to tag each book's selling season, estimate the optimal buy month (when prices are at trough), and predict the target sell window.

This context appears directly in the deal view and is factored into the "List at" price calculation. A deal found in October for a spring-semester textbook is evaluated differently from the same book found in February — the platform knows the difference and adjusts both the recommended hold strategy and the expected peak price.

### 5. Deals Dashboard

The central user interface is a real-time dashboard presenting filtered, sorted, and ranked arbitrage opportunities. Each deal shows:

- Current price vs. 1-year average (discount percentage)
- Recommended listing price and expected profit
- Margin and ROI
- Sales rank and rank trend
- Offer count trend (rising competition = warning signal)
- Seller trust score (derived from Amazon seller ratings via Wilson Score confidence interval)
- Deal Trust score (the percentage of offer drops that correlated with confirmed sales — a measure of how reliable the profit estimate is)
- Amazon restriction status (whether the user is approved to sell this specific book in this condition)
- Seasonality classification

The dashboard updates in real time. A background polling mechanism checks for new deals every 60 seconds and notifies users with a context-aware banner when fresh opportunities matching their active filters appear — without disrupting their current view.

**Smart Filtering.** Users can filter by profit floor, ROI threshold, sales rank ceiling, deal trust percentage, seller trust score, price drop percentage, and rank drop frequency. A one-click "Optimal Filters" preset applies a tuned set of criteria designed to surface the highest-quality opportunities.

**Self-Aware Tooltips.** Hovering any column header or filter label shows a contextual explanation generated by the platform's own AI reading its own documentation. These are cached for instant load. Users discover the meaning of every metric without leaving the dashboard.

**Data Hygiene.** A background "Janitor" process removes any deal not refreshed within 72 hours, preventing stale opportunities from cluttering the feed.

### 6. Amazon Restriction (Gating) Check

Not every seller can sell every book on Amazon. Category and brand restrictions vary by account and condition. The platform integrates directly with Amazon's Selling Partner API to check each user's specific approval status for each deal, in the exact condition (Used – Like New, Used – Very Good, etc.) being recommended.

Restricted items are flagged with a direct link to the approval application in Seller Central. Approved items show a "Buy Now" button linking directly to the product listing. Users can filter out restricted items entirely to see only immediately actionable deals.

### 7. My Mentor (AI Deal Analysis)

Expanding any deal opens an AI analysis overlay. **My Mentor** delivers 50–80 words of specific, actionable guidance on that exact deal — accounting for the book's actual metrics, the platform's accumulated arbitrage knowledge, and the current market context.

Users choose from four AI advisor personas, each with a distinct perspective:

- **CFO (Olyvia):** Risk-averse, focused on capital protection and reliable return
- **Flipper (Joel):** Speed and volume oriented, prioritizes fast turnover
- **Professor (Evelyn):** Educational, explains the reasoning behind the recommendation
- **Quant (Errol):** Data-driven, statistical, focused on probability and trend analysis

The active persona is synchronized across the deal overlay and the persistent Mentor Chat interface, so the same advisor voice follows the user through their session.

### 8. Mentor Chat

A persistent AI chat interface — accessible from the navigation bar at any time — lets users ask free-form questions about deal strategy, market conditions, business decisions, or Amazon selling mechanics. The chat uses the same persona system as My Mentor and is informed by the platform's full accumulated knowledge base. It functions as an always-available business advisor with full context about how the platform works and what it has learned.

### 9. Tracking: Potential Buys, Active Inventory, and Sales & Profit

The Tracking page closes the loop from deal discovery to realized revenue. It is the operational counterpart to the dashboard — where deals become purchases, purchases become inventory, and inventory becomes settled sales. The page is functional today; UX refinements are in active development against the findings of the May 2026 competitor audit.

**Potential Buys.** Once a user commits to a deal, it lands in Potential Buys with its estimated profit, margin, and ROI carried over. The user enters their actual buy cost inline at the point of purchase, which flags the row as confirmed and recalculates all downstream math against the real number. This is the lead-stage workflow that sourcing-only competitors omit entirely.

**Active Inventory.** Every unit at Amazon is tracked by fulfillment state (Fulfillable, Inbound Working, Inbound Shipped, Inbound Receiving) with full identification (ASIN, SKU, title, condition) and the confirmed buy cost. Both ASIN and SKU are hyperlinked — ASIN to the Amazon product page, SKU to the Seller Central inventory view filtered to that SKU. The tab-hopping that competitor tools force on users is eliminated.

**Sales & Profit.** Every realized sale is matched via FIFO to its original buy-cost row in inventory, producing true realized profit per unit. The same profit-calculation logic that drives the dashboard's projections drives the realized-profit math here — there is no second source of truth, and reconciliation drift against Amazon's deferred fee posting (a chronic complaint about InventoryLab and Sellerboard) is avoided by computing realized profit from confirmed cost and confirmed sale price rather than from estimated fees.

### 10. How the AI Gets Smarter (Trade Secret)

The platform's AI does not rely on a static training set. It is continuously updated against a curated knowledge base of arbitrage strategies and market intelligence specifically tuned to online used-book arbitrage. This knowledge base has two layers:

- **Strategies:** Specific, quantitative rules — the "if-then" logic of profitable arbitrage.
- **Intelligence (mental models):** Qualitative frameworks for understanding market dynamics — how categories behave, how seasonality interacts with rank, how price tiers form, why certain books behave differently than others.

This knowledge is distilled from expert sources, refined through operational experience, and homogenized periodically to merge redundancies and keep the dataset concise. The result: when My Mentor evaluates a deal, when Mentor Chat answers a question, when the Agent's Choice mastermind ranks the top opportunities of the day, the AI is reasoning against expert-curated, niche-specific knowledge rather than against generic e-commerce heuristics.

The mechanism for keeping this knowledge current is proprietary and considered a core competitive moat. Competitors who deploy AI in their products typically use it for narrow tasks (rank prediction, basic classification, generic LLM chat). None of the tools we audited combine a continuously refreshed, niche-specific knowledge base with multi-persona reasoning the way Agent Arbitrage does.

---

## Competitive Position

A May 2026 audit of seven directly comparable tools — ZenArbitrage, Tactical Arbitrage, SellerAmp / SAS, ScoutIQ, BookMine, InventoryLab, and Sellerboard — establishes Agent Arbitrage's position.

### Category Map

| Category | Tools | Strengths | Gaps Agent Arbitrage Closes |
|---|---|---|---|
| **Book-niche sourcing** | ZenArbitrage, ScoutIQ, BookMine | Book-focused deal discovery | Curated profit-validated deals; AI reasoning; tracking integration |
| **Generalist sourcing** | Tactical Arbitrage, SellerAmp / SAS | Broad product coverage, large feature sets | Book-specific intelligence; inferred-sale pricing; tracking; AI mentor |
| **Post-buy tracking** | InventoryLab, Sellerboard | Inventory accounting and P&L | Curated sourcing integration; inferred-sale pricing; AI advisor; fee reconciliation drift |

**Key finding:** Only InventoryLab and Sellerboard have real post-buy tracking. The other five are pre-buy sourcing tools that either omit tracking entirely (SellerAmp explicitly admits no sales dashboard) or treat it as an afterthought (ZenArbitrage). No tool in the audit covers the full loop natively — every comparable user workflow requires combining at least two of these tools plus a spreadsheet and Seller Central.

### Feature Comparison (Selected)

| Capability | Agent Arbitrage | InventoryLab | Sellerboard | Tactical Arbitrage | SellerAmp | ZenArbitrage |
|---|---|---|---|---|---|---|
| Curated deals (profit-validated, AI-screened) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Inferred Market Clearing Price (3-yr verified transactions) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| AI reasonableness check on recommended prices | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Niche-trained AI advisor (multi-persona) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Continuously curated arbitrage knowledge base | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Per-deal gating check (SP-API, condition-specific) | ✅ | ❌ | ❌ | ❌ | Partial | ❌ |
| Potential Buys → Active Inventory → Sales loop | ✅ | Partial | Partial | ❌ | ❌ | Partial |
| FIFO realized profit | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Fee reconciliation drift | None (avoided by design) | Acknowledged | Acknowledged | N/A | N/A | N/A |
| Browser-only, work-from-anywhere | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Competitor AI Use — Honest Read

The "we use AI" claim is now table-stakes in this category, but actual deployment in the audited tools is narrow. Per public product documentation and third-party reviews as of May 2026:

- **Sellerboard** centers on profit reporting, automated alerts, and review-request workflows. Its AI surface area is operational automation, not reasoning about deal quality.
- **Tactical Arbitrage** describes its core sourcing as a "search algorithm" applied across 1,400+ retailer sites. The one feature it markets as AI-powered is its TA Box Calculator (shipment optimization), not its sourcing or pricing logic.
- **InventoryLab** has minimal AI surface area. Its strength is accounting integration, not reasoning.
- **ZenArbitrage, SellerAmp, ScoutIQ, BookMine** are calculator and scanner tools. They surface metrics; they do not reason about them.

None of the audited competitors combine: (a) AI reasoning as a *gate* on their own pricing math, (b) a continuously curated niche knowledge base, (c) multi-persona reasoning interfaces, and (d) AI rescue for hidden-sale detection. Agent Arbitrage does all four.

### Where Competitors Are Stronger
Honest framing for investor diligence:

- **InventoryLab and Sellerboard** have mature accounting features (multi-marketplace, VAT, reimbursement tracking, settlement reconciliation, dedicated PPC dashboards). Agent Arbitrage does not currently target these features because they fall outside the niche.
- **Tactical Arbitrage** has much broader product coverage. This is a deliberate non-target — Agent Arbitrage is focused on books, not generalist arbitrage.
- **ScoutIQ** has best-in-class mobile-scanning UX for in-store sourcing. Agent Arbitrage's niche is online sourcing (US prep warehouse model) and does not compete in this segment.

These gaps do not apply to the target customer: an international or domestic seller running an online used-book arbitrage operation against the US Amazon marketplace through a prep warehouse.

---

## Architecture & Reliability

The platform runs on a lean, cost-efficient infrastructure stack. The current deployment operates on a $6/month VPS and is engineered to scale to 10,000+ subscribers through defined infrastructure upgrade tiers rather than premature over-engineering.

**API Token Management.** The platform implements a sophisticated "Controlled Deficit" strategy for managing third-party data API consumption — leveraging allowances for temporary token deficits to maximize data throughput without hitting rate limits or lockouts. A shared token state coordinates between concurrent background processes. A hard deficit floor prevents the system from reaching lockout thresholds. If token recharge will take longer than 60 seconds, the system releases its processing lock and routes background workers to other tasks rather than sitting idle.

**State Persistence.** Critical system state — including the data watermark that tracks which products have been processed — is stored in the database rather than in memory or local files. The system can resume exactly where it left off after a restart or deployment.

**Data Integrity by Default.** Deals with zero or negative profit, missing pricing data, or failed AI validation are retained in the database but filtered from the user interface. The system heals incomplete records naturally as new data arrives, rather than discarding and endlessly re-fetching.

**Amazon SP-API Integration.** The platform uses a modern, simplified Amazon authentication flow relying solely on Login with Amazon (LWA) refresh tokens, eliminating the complexity and failure modes of AWS IAM credential signing.

---

## Scalability Roadmap

Infrastructure is planned around explicit subscriber growth milestones:

| Phase | Subscribers | Infrastructure | Monthly Cost |
|---|---|---|---|
| Launch | 0–200 | Single VPS (1 vCPU / 4GB RAM) | ~$6 |
| Growth | 200–1,000 | Upgraded VPS (4 vCPU / 16GB RAM) | ~$25 |
| Scale | 1,000–5,000 | Split web + worker servers, PostgreSQL | ~$80–100 |
| Enterprise | 5,000+ | Load-balanced multi-node architecture | TBD |

The SQLite-to-PostgreSQL migration at the Scale tier is the only significant architectural change in the roadmap. All other upgrades are configuration-level adjustments. The codebase is written to support this migration without a rewrite. Load testing on the current Launch-tier hardware established a baseline of 295 requests/second with 137ms p95 latency.

---

## Target Market

**Primary persona:** Online used-book arbitrage sellers operating against the US Amazon marketplace, including:

- US-based sellers running a home-based operation with their own prep
- US-based sellers using a third-party prep warehouse
- **International sellers** (Canada, UK, EU, Australia, elsewhere) selling into the US market via a US prep partner

The platform's browser-only architecture and elimination of on-premise dependencies make it a natural fit for the international "work-from-anywhere" operator — a customer segment underserved by tools designed around in-store mobile scanning.

**Niche focus:** Used textbooks and scholarly non-fiction. The seasonality intelligence, the inferred-sale pricing logic, and the AI knowledge base are all tuned to the behaviors of this category. The platform is not a generalist arbitrage tool and will not be positioned as one.

---

## Access Control

The platform operates on a two-tier access model:

**Users** access the Deals Dashboard, deal details and AI analysis, Mentor Chat, the Tracking page, and their personal settings (cost structure, API credentials).

**Operators** additionally maintain the AI knowledge base, review newly extracted strategies and intelligence, and manage the data query configuration. These operational controls are the mechanism that keeps the AI continuously sharpened against current market knowledge and are not exposed in the user-facing product.

---

## Current Status

Agent Arbitrage is in active pre-launch development as of May 2026, running at [agentarbitrage.co](https://agentarbitrage.co). The core deal discovery, AI analysis, dashboard, and Tracking features are fully functional.

Recent milestones:

- **March 2026:** Pricing integrity update — 100% of profit projections now based on verified transaction data; all listing-average fallbacks removed.
- **March 2026:** Hard pricing safety ceiling ($1,500) implemented to prevent acceptance of manipulated or anomalous market prices.
- **April–May 2026:** FBA inventory and sales tracking via Amazon SP-API; FIFO realized-profit matching; editable buy-cost workflow with confirmation flag. The Tracking page is functional and shipping iteratively — UX/UI refinements informed by the May 2026 competitor audit are ongoing.
- **May 2026:** Unified pagination across Dashboard and Tracking; "Self-Aware Tooltips" rolled out across the dashboard.

Next milestones (pre-launch): SP-API client secret rotation, the addition of a 180-day offer-count column, Predictive Buy-In Window Alerts, and an Access Card / Code exclusion filter.
