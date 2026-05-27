# Tracking Page UX Audit — Competitor Research & Pain Points

**Status:** Research complete. Feeds the Tracking page UX Overhaul & Bug Fixes implementation work.
**Original task:** Trello Card 1 — "[P2] Tracking Page UX Research — Competitor Audit & Pain Points"
**Date of research:** May 22, 2026
**Canonical location:** `Documentation/Business_Documents/Research/Tracking_UX_Audit.md`
**Related source docs:** `Feature_Tracking.md`, `Agent_Arbitrage_Product_Overview.md`

---

## TL;DR

**The market opportunity is bigger than the card framed it.** Of the 6 competitors audited, only 2 (InventoryLab, Sellerboard) have real post-buy tracking pages. The other 4 (ZenArbitrage, Tactical Arbitrage, SellerAmp, ScoutIQ, BookMine) are pre-buy sourcing tools that either omit tracking entirely (SellerAmp explicitly admits "no sales dashboard") or offer thin tracking as an afterthought (ZenArbitrage). **A cottage industry of paid Excel/Google Sheets templates exists precisely because no tracker fully solves the problem** — Caleb Roth's free spreadsheet has 155 ratings; multiple Gumroad sellers charge $14-$50 for FBA tracking templates.

This means AgentArbitrage's Tracking page isn't competing against a polished baseline — it's competing against a fragmented mess of "sourcing tool + spreadsheet + Seller Central tab-hopping." If the three tabs (Potential Buys / Active Inventory / Sales & Profit) tie sourcing → inventory → realized profit in one place with the pain points below fixed, this becomes a real differentiator versus competitors and not just feature parity.

---

## 1. Feature Matrix

Rows = the three AgentArbitrage tracking tabs. Columns = competitors. Cells = what each tool actually offers in that scope (not what they market — what's documented).

| Tab equivalent | ZenArbitrage | InventoryLab (Stratify) | Tactical Arbitrage | SellerAmp SAS | ScoutIQ | BookMine | Sellerboard *(added)* |
|---|---|---|---|---|---|---|---|
| **Potential Buys** (sourcing leads → confirmed inventory) | Has "Tracking" page; mark as purchased; book + buy cost + status. Lead-buying via Z-Bay. | "Batch" workflow — enter buy cost, supplier, date during listing; estimated net profit per item before listing. | "Folder Updates" — save items, auto-update daily, ROI/profit alerts, in-stock notifications. No formal "Potential Buys" — folders are the lead bucket. | Notes + Tags panel — sourcing database with custom tags. "Add to Inventory" button exists, but no real lead-pipeline UI. | "Suggested Accept Lists" — track items marked Accept during scanning. Mobile-first; not a desktop pipeline view. | Not present. BookMine is purely deal-discovery. | Not really — assumes inventory is already in Amazon. Some inventory planning but no lead-stage. |
| **Active Inventory** (units at Amazon, costs, value) | Tracks purchases; "mark received"; cost lookup; book-level. No FBA stock counts pulled. | Yes — full inventory page, in-stock value, sales value, accounting per unit; integrates with Send-to-Amazon. | "View Inventory" — sees own FBA inventory; password-protected. Surface-level. | None — explicitly no inventory tracking. Sourcing tool only. | None — scanning tool only. Has "is this already in your inventory" lookup during scan but no inventory page. | None. | Yes — strong. Per-ASIN portfolio data, COGS, shipping profile, VAT, profit-per-unit; flags negative-margin SKUs. |
| **Sales & Profit** (post-sale realized profit, fees, FIFO) | Built-in profit tracking; auto-calculates from sales; export to spreadsheet. Books-focused. | P&L report, automated COGS, FIFO matching, Date Range Summary; **acknowledged discrepancies vs. Amazon due to deferred posting**. | None native — relies on InventoryLab integration. | None. | None. | None. | **The category leader.** Order-level reconciliation (not estimated from settlements); FBA + referral + storage + LTSF fees; same-day fee-change detection; PPC included; eBay multi-channel; Money Back module for reimbursements. |

**Key takeaway:** Only InventoryLab and Sellerboard truly cover all three. ZenArbitrage covers all three thinly. Everyone else is a sourcing tool that punts on tracking.

---

## 2. Pain Points

Ranked by frequency observed across reviews, support forums, blog complaints, and our own use. Top 10:

**1. Real fees vs. estimated fees never match Amazon.** InventoryLab's own support docs admit their numbers won't match Amazon's because they use "payments" data not "sales" data, and Amazon's deferred transaction posting (DD+7 reserves) creates 2+ week lags. Sellerboard's marketing leans hard on solving this. Sellers report dashboard profit values that swing wildly during reconciliation windows. *Confirms your own bug suspicion — Sales & Profit showing $0.00 fees is the same family of problem.*

**2. Cost entry is the universal hairball.** Every tool struggles with where buy-cost comes from. InventoryLab tries to capture it during the listing batch but breaks when items arrive without going through their batch flow. Sellerboard requires manual COGS entry per SKU and is "garbage in, garbage out." ZenArbitrage requires marking items as purchased. *Your "Download Missing Costs CSV / Upload Costs (CSV)" workflow is the same problem — and it's opaque (per your card). InventoryLab solves it with an in-app cost-entry table; Sellerboard with a per-SKU edit row.*

**3. Lookup-the-ASIN-or-SKU is a tab-hopping nightmare.** Sellers complain about "repeated clicks, SKU checks, barcode management" (Descartes Finale marketing literally sells against this). The Seller Assistant SKU tool was built specifically because "status, cost breakdown, and listing history visible per SKU without opening Seller Central" is a feature people will pay for. *Maps directly to your pain point: ASIN/SKU not linked anywhere.*

**4. Amazon-side data gaps cascade into tracker bugs.** Amazon's `GET_FBA_INVENTORY_PLANNING_DATA` API has documented missing-SKU bugs (active GitHub issue, Nov 2025). Tools that pull from this report inherit the gaps. Result: a tracker can show an SKU has 0 units when Amazon shows 5. *Worth knowing when you debug Sales & Profit fees showing $0 — may not be your bug.*

**5. Pagination + sort UI is inconsistent and unsorted across tools.** Caleb Roth's tracking spreadsheet's selling point is "you can sort it any way you want" — meaning the tools cannot. ScoutIQ, ZenArbitrage, BookMine all have minimal column sorting. *Your gripe (no sort arrows, inconsistent pagination styles) is industry-standard mediocrity — fixing it cleanly is a small differentiator.*

**6. Reconciliation discrepancies (returns, refunds, reimbursements).** Reviews repeatedly call out that "profit" shown is wrong because returns post 2-30 days after the sale, reimbursements weeks later. InventoryLab and Sellerboard both handle FIFO COGS but warn users that historical profit numbers will change retroactively. No tool surfaces a clear "this is the reconciled number / this is the estimate" distinction in the UI. *Direct opportunity for AgentArbitrage: visibly tag numbers as Estimated vs. Reconciled.*

**7. Labels and buttons are unintuitive even to power users.** Multiple reviews note InventoryLab's UI was redesigned and is now worse ("can't find listing settings", "supplier reset on every listing"). ScoutIQ users complain triggers are buried. Sellerboard has "feels overwhelming, still discovering new ones" reviews even from happy users. *Your "button labels on Active Inventory are unclear even to the builder" pain point is universal — and a low-hanging differentiator.*

**8. Mobile/desktop split forces double workflow.** Scoutify, ScoutIQ, Scoutly all live on mobile; trackers live on desktop. Sellers do their cost entry on phones at thrift stores, then redo it on desktop. *Probably out of scope for v1 but worth noting for roadmap.*

**9. No "what should I rebuy?" signal.** Tools track sales but don't suggest replenishment of repeatable winners. Sellerboard, RestockPro, and Boxem all try; reviews say their reorder logic is too crude for books (where each ASIN is typically a single-unit play, not a replenishable). *Potential AgentArbitrage edge — Pass-2 LLM evaluation already understands "year-round vs textbook seasonal" — feed that signal into Sales & Profit to flag "this ASIN reorderable?".*

**10. No clear FIFO surfacing per-unit.** InventoryLab does FIFO matching but doesn't show users which exact buy-cost record matched to which sale. When a buyer asks "how much did I really make on order X", sellers cannot trace it. *Opportunity to show the FIFO match-line directly in Sales & Profit detail.*

---

## 3. Recommendations

### Add (high-confidence, low-effort wins)

- **Hyperlink every ASIN and SKU** in all three tabs to the relevant Amazon page. ASIN → `https://www.amazon.com/dp/{ASIN}`, SKU → Seller Central Manage Inventory deep-link `https://sellercentral.amazon.com/inventory?searchType=sku&searchValue={SKU}`. *No competitor does this cleanly; it's a one-line fix.*
- **Add sort arrows to every column** in all three tabs, matching the Dashboard's `^v` pattern. Consistency across pages is a credibility signal users notice.
- **Add ASIN column to Active Inventory.** Trivial to add since the data is in the same record.
- **Add Profit + ROI/Margin columns to Potential Buys.** Pull from the Pass-2 evaluation results that are already calculated.
- **Unify pagination style** between Dashboard and Tracking. Pick one — the Dashboard's numbered 1-5 + Prev/Next style is the better UX (matches Amazon Seller Central, matches search results pattern users see daily).
- **Tag profit numbers as Estimated vs. Reconciled.** Tiny visual marker (e.g., italic or a small badge) on rows where Amazon hasn't fully posted yet. No competitor does this; multiple complain about it.

### Add (medium-effort, larger payoff)

- **Inline cost editing in Active Inventory** with auto-save. Eliminates the opaque "Download Missing Costs CSV / Upload Costs CSV" round-trip for the common case. Keep CSV upload for bulk; make it a secondary action.
- **Show the FIFO match line** in Sales & Profit detail — which inventory record's buy-cost was used for each sold unit. Removes the "is this number trustworthy?" question.
- **"Reorderable?" flag on Sales & Profit rows.** Use the Pass-2 evaluation's season/velocity signal to mark whether the ASIN is a one-off vs. a replenishable. None of the book-focused trackers do this.

### Skip (don't build)

- **Don't build mobile scouting.** ScoutIQ, Scoutify, BookMine, Bookzy all own this; not your differentiation lane.
- **Don't build PPC management or repricing.** Sellerboard, Helium 10, BQool all do this; out of scope for a deal-discovery tool's tracking page.
- **Don't try to build a full P&L / accounting export.** Sellers use QuickBooks for that; trying to be both will dilute the product.
- **Don't build VA/team management features** (multi-user, role-based). Out of scope for solo builder personas.

### Do differently (positioning)

- **Frame the Tracking page as "deal-discovery to realized profit, in one timeline."** That's the loop competitors cannot close: Pass-1/Pass-2 finds the deal → user buys → Active Inventory holds the cost → Sales & Profit reconciles the actual outcome → that feedback can loop back to refine future picks. None of the 6 audited competitors connect those steps.
- **Show one source of truth, with reconciliation status clearly marked.** Don't hide the messiness of Amazon's deferred posting — surface it. The honesty becomes a trust feature.

---

## Sources & evidence trail

**Competitor docs / reviews (most useful):**
- ZenArbitrage tutorial — vovaeven.com/blog/zen-arbitrage-complete-tutorial-and-review
- InventoryLab support: "InventoryLab Does Not Match Amazon" — inventorylab.threecolts.support
- InventoryLab P&L discrepancies — support.inventorylab.com
- Sellerboard vs InventoryLab — vovaeven.com/blog/sellerboard-vs-inventorylab-review
- Sellerboard review (depth) — emarketinghacks.com/sellerboard-review/
- SellerAmp Garlic Press Seller review (explicit "no sales dashboard") — garlicpressseller.com
- Tactical Arbitrage's reliance on IL integration — cleartheshelf.com, tacticalarbitrage.com
- ScoutIQ feature page — scoutiq.co/features
- BookMine — bookmine.co

**Pain-point evidence:**
- Amazon SP-API missing-SKU GitHub issue — github.com/amzn/selling-partner-api-models/issues/5044
- Amazon Inventory Reconciliation: Manual vs. Automation Costs — webgility.com (Feb 2026)
- InventoryLab Seller Central forum complaints — sellercentral.amazon.com/seller-forums (Jan 2025)
- Seller Assistant SKU tool (positioned against tab-hopping) — sellerassistant.app/tools/skus
- Caleb Roth Book Flipper tracking spreadsheet (155 ratings) — thebookflipper.com/tracking-spreadsheet
- Multiple Gumroad spreadsheet sellers (Hustlin Hooks $50, Catalystic Worx, etc.) — proves spreadsheet workaround pattern

**Notable trusted FBA voices for follow-up if needed:**
- Caleb Roth (The Book Flipper) — book-flipping focused, has tracking spreadsheet
- Garlic Press Seller — honest tool reviews
- vovaeven.com — long-form tool comparisons
- emarketinghacks.com — depth Sellerboard analysis

**Communities (not searched directly — paywalls / FB groups not crawlable):**
- r/FulfillmentByAmazon
- Amazon FBA High Rollers (Helium 10 sponsored)
- MySilentTeam (73,000 members, Jim Cockrum)
- Helium 10 Members Group (40,000+)
- Worth a direct visit before Card 2 if you want firsthand quotes.

**CSV filter results:** 97 of 813 rows matched tracking-relevant keywords, but content was overwhelmingly Keepa/sourcing-focused, not tracking-pain-points. One useful lead: r/Flipping thread on developing a book price tracking tool. Recommend a separate, focused CSV pass with tracking-specific keywords if you want a deeper second sweep.
