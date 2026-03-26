# Agent Arbitrage: Product Overview

**Version 3.4 — March 2026**

---

## What It Is

Agent Arbitrage is an AI-powered deal intelligence platform for Amazon FBA booksellers. It continuously monitors the Amazon marketplace, identifies used books trading significantly below their historical sale prices, calculates true net profit on each opportunity, and delivers ranked, filtered deal recommendations — in real time, around the clock, without manual research.

The platform sits at the intersection of market data analytics, machine learning, and operational workflow tooling. It replaces hours of manual product research with a self-maintaining pipeline that surfaces only high-confidence, profitable deals — and explains exactly why each one qualifies.

---

## The Problem It Solves

Used book arbitrage on Amazon is a proven business model: buy used books below market value, resell them on Amazon FBA at a profit. The challenge is scale. Identifying genuinely profitable inventory requires cross-referencing sales history, pricing trends, seasonal demand, seller competition, Amazon's own pricing behavior, and your personal cost structure — for thousands of potential products simultaneously.

Manual research is slow, prone to error, and incapable of acting on market movements in real time. Most sellers either under-invest in research (missing deals) or rely on tools that show raw data without context (leading to bad buys).

Agent Arbitrage automates the entire discovery-to-decision pipeline and layers AI judgment on top of it.

---

## Core Capabilities

### 1. Continuous Deal Discovery

The platform runs a background data engine that continuously queries the definitive Amazon pricing history database on a minute-by-minute basis. It scans for products whose current used price has dropped meaningfully below their established historical average.

This isn't a simple price comparison. The system distinguishes between:

- Products that sell reliably vs. those with inflated or stale list prices
- Active deals with real buyer demand vs. dead inventory sitting unsold
- Genuine price dips vs. pricing errors or manipulation

Every candidate product goes through a multi-stage validation pipeline before it appears in the user's dashboard. Products that fail validation are retained in the background database for monitoring but are never surfaced to users — maintaining a clean, high-signal feed.

### 2. Inferred Sale Pricing (The Core Innovation)

The platform's pricing logic is built on a proprietary concept: **inferred sales**. Rather than relying on list prices or average asking prices (which can be inflated or stale), the system reconstructs actual historical transactions by correlating two independent data signals:

- A drop in offer count — indicating a unit was purchased
- A corresponding drop in sales rank — confirming Amazon registered the transaction

When both signals occur closely together, a sale is confirmed. The price at that moment is recorded as a verified transaction price. All profit calculations are derived exclusively from these verified prices.

For products where the standard detection method finds no sales (e.g., sellers with deep inventory where offer count doesn't drop after each sale), an AI-powered rescue mechanism analyzes historical rank and price data to identify "hidden sales" — rank improvements that indicate purchases even without observable offer count changes.

### 3. AI-Validated Pricing & Profit Calculation

Every deal's recommended listing price passes through a multi-layer validation pipeline before reaching the user:

**Peak Season Pricing.** The system identifies each product's historical peak selling season and calculates the mode price during that period — the price sellers most frequently achieved, not a mathematical average. For textbooks, this correctly captures semester-driven price spikes that can be 200–400% above off-peak pricing.

**Amazon Price Ceiling.** The recommended listing price is automatically capped at 90% of Amazon's own new price across current, 6-month, and 12-month averages. This ensures every deal remains competitive against Amazon's direct sales.

**AI Reasonableness Check.** Each pricing recommendation is validated by an AI reasoning model, which reviews the product's title, category, binding, page count, and sales rank to determine whether the projected price is credible. Prices above $1,500 are automatically rejected. Prices more than 3x the current used price trigger mandatory AI scrutiny.

**Business Math.** The platform calculates all-in acquisition cost (purchase price, tax, prep fee, shipping to Amazon), net profit after Amazon's FBA and referral fees, margin percentage, and minimum viable listing price — personalized to each user's cost structure entered in their settings.

### 4. Seasonality Intelligence

Amazon book sales are highly seasonal. Textbooks spike at semester start. Test prep materials surge before exam seasons. Reference books follow professional certification cycles. The platform uses AI classification to tag each product's selling season, estimate the optimal buy month (when prices are at trough), and predict the target sell window.

This context appears directly in the deal dashboard and is factored into the "List at" price calculation. A deal found in October for a spring-semester textbook looks very different from the same book found in February — the platform knows the difference.

### 5. Deals Dashboard

The central user interface is a real-time deals dashboard presenting filtered, sorted, ranked arbitrage opportunities. Each deal shows:

- Current price vs. 1-year average (the discount percentage)
- Recommended listing price and expected profit
- Margin and ROI
- Sales rank and rank trend
- Offer count trend (rising competition = warning signal)
- Seller trust score (derived from Amazon seller rating data using a statistical Wilson Score confidence interval)
- Deal Trust score (the percentage of offer drops that correlated with confirmed sales — a measure of how reliable the profit estimate is)
- Amazon restriction status (whether the user is approved to sell that specific product in that condition)
- Seasonality classification

The dashboard updates in real time. A background polling mechanism checks for new deals every 60 seconds and notifies users with a banner when new opportunities matching their active filters have appeared — without disrupting their current view.

**Smart Filtering.** Users can filter by profit floor, ROI threshold, sales rank ceiling, deal trust percentage, seller trust score, price drop percentage, and rank drop frequency. A one-click "Optimal Filters" preset applies a tuned set of criteria designed to surface the highest-quality opportunities (as of February 2026: minimum $45 profit, 20%+ ROI, rank under 1M, 2+ rank drops in 30 days, 70%+ deal trust, 5/10+ seller trust, 10%+ below average, with Amazon and gated items hidden).

**Data Hygiene.** A background "Janitor" process runs every 4 hours and removes any deal not refreshed within 72 hours. This prevents the dashboard from accumulating stale opportunities that are no longer actionable.

### 6. Amazon Restriction (Gating) Check

Not every seller can sell every product on Amazon. Category and brand restrictions — called "gating" — vary by seller account and product condition. The platform integrates directly with Amazon's Selling Partner API to check each user's specific approval status for each deal, in the specific condition (Used - Like New, Used - Very Good, etc.) being recommended.

Restricted items are flagged with a direct link to apply for approval in Seller Central. Approved items show a "Buy Now" button linking directly to the product listing. Users can filter out restricted items entirely to see only immediately actionable deals.

### 7. My Mentor (AI Deal Analysis)

Expanding any deal opens an AI-powered analysis overlay. **My Mentor** delivers specific, actionable guidance on that deal — accounting for the product's actual metrics, the user's learned strategies, and the current market context.

Users choose from four AI advisor personas, each bringing a distinct perspective:

- **CFO (Olyvia):** Risk-averse, focused on capital protection and reliable return
- **Flipper (Joel):** Speed and volume oriented, prioritizes fast inventory turnover
- **Professor (Evelyn):** Educational, explains the reasoning behind the recommendation
- **Quant (Errol):** Data-driven, statistical, focused on probability and trend analysis

The active persona is synchronized across the deal overlay and the My Mentor Chat interface, so the same advisor voice follows the user throughout their session.

### 8. My Mentor Chat

A persistent AI chat interface — accessible from the navigation bar at any time — allows users to ask free-form questions about deal strategy, market conditions, business decisions, or Amazon selling mechanics. The chat uses the same persona system as My Mentor and is informed by the platform's full accumulated knowledge base (strategies and mental models developed through real-world operation). It functions as an always-available business advisor with full context about how the platform works and what it has learned.

### 9. Guided Learning (Admin)

The platform learns. An admin-accessible knowledge refinement system allows operators to continuously expand and sharpen the AI's understanding of the market. Proprietary insights — developed through hands-on FBA operation, direct market observation, and accumulated deal analysis — are distilled into two types of structured knowledge:

- **Strategies:** Specific, quantitative rules. ("Buy if Sales Rank < 50,000 and Profit > $10")
- **Mental Models (Intelligence):** Qualitative frameworks for understanding market dynamics. ("Textbooks have a U-shaped sales rank curve tied to academic calendars")

All knowledge is reviewed and approved before being committed to the knowledge base. Once in the system, it informs My Mentor's deal analysis and My Mentor Chat's responses — effectively allowing the platform's AI to be trained on expert knowledge without any code changes.

A Semantic Homogenization process runs weekly, using AI to merge duplicate or synonymous concepts that accumulate over time, keeping the knowledge base concise and high-quality.

---

## Architecture & Reliability

The platform runs on a lean, cost-efficient infrastructure stack. The current deployment operates on a $6/month VPS and is engineered to scale to 10,000+ subscribers through defined infrastructure upgrade tiers rather than premature over-engineering.

**API Token Management.** The platform implements a sophisticated "Controlled Deficit" strategy for managing third-party data API consumption — leveraging allowances for temporary token deficits to maximize data throughput without hitting rate limits or lockouts. A shared token state coordinates between concurrent background processes, and a hard deficit floor prevents the system from ever reaching lockout thresholds. If token recharge will take longer than 60 seconds, the system releases its processing lock and routes background workers to other tasks (like restriction checks or data cleanup) rather than sitting idle.

**State Persistence.** Critical system state — including the data watermark that tracks which products have been processed — is stored in the database rather than in memory or local files, ensuring the system can resume exactly where it left off after a restart or deployment.

**Data Integrity by Default.** Deals with zero or negative profit, missing pricing data, or failed AI validation are retained in the database but filtered from the user interface. This allows the system to heal incomplete records naturally as new data arrives, rather than discarding and endlessly re-fetching the same products.

**Amazon SP-API Integration.** The platform uses a modern, simplified Amazon authentication flow that relies solely on Login with Amazon (LWA) refresh tokens, eliminating the complexity and failure modes of AWS IAM credential signing.

---

## Scalability Roadmap

The infrastructure is planned around explicit subscriber growth milestones:

| Phase | Subscribers | Infrastructure | Monthly Cost |
|---|---|---|---|
| Launch | 0–200 | Single VPS (1 vCPU / 4GB RAM) | ~$6 |
| Growth | 200–1,000 | Upgraded VPS (4 vCPU / 16GB RAM) | ~$25 |
| Scale | 1,000–5,000 | Split web + worker servers, PostgreSQL | ~$80–100 |
| Enterprise | 5,000+ | Load-balanced multi-node architecture | TBD |

The transition from SQLite to PostgreSQL at the Scale tier is the most significant architectural change. All other upgrades are configuration-level adjustments. The codebase is written to support this migration without a rewrite.

---

## Access Control

The platform operates on a two-tier access model:

**Users** access the Deals Dashboard, deal details and AI analysis, My Mentor Chat, and their personal settings (cost structure, API credentials).

**Admins** additionally access the knowledge refinement system, the Strategies and Intelligence knowledge bases, and the data query configuration. Administrative features that could cause data loss or system instability are managed via controlled backend processes rather than exposed in the UI.

---

## Current Status

Agent Arbitrage is in active pre-launch development as of March 2026, running at [agentarbitrage.co](https://agentarbitrage.co). The core deal discovery, AI analysis, and dashboard features are fully functional. The platform has been load-tested at 295 requests/second on the current infrastructure with 137ms p95 latency on standard operations.

Recent milestones include a March 2026 pricing integrity update (ensuring 100% of profit projections are based on verified transaction data), the addition of FBA inventory tracking via Amazon SP-API, and the implementation of hard pricing safety ceilings to prevent AI-assisted analysis from accepting manipulated or anomalous market prices.
