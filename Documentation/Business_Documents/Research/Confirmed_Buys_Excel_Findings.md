# Confirmed Buys — Excel Template Findings

**Status:** Research complete. Feeds the Confirmed Buys (fourth Tracking tab) design work.
**Source artifact:** `Master_Template_Agent_Arbitrage_v19-Shipping_Included.xlsm` (pre-app-era template, 6 sheets, 1.27k columns on the data sheets, mostly empty rows).
**Canonical location (proposed):** `Documentation/Business_Documents/Research/Confirmed_Buys_Excel_Findings.md`
**Related docs:** `Feature_Tracking.md`, `INFERRED_PRICE_LOGIC.md`, `Data_Logic.md`, `Tracking_UX_Audit.md`.

---

## TL;DR

The Excel encodes a **three-track row model** — one row per book carrying three parallel sets of profit columns: **pre-purchase estimated** (HN–HQ), **post-purchase actual** (IC–IH), and **post-sale realized** (IY–JF). The current app already has track 1 (Dashboard estimates) and track 2 (`buy_cost_confirmed` on Potential Buys / Active Inventory), and a thin track 3 (Sales & Profit). The Confirmed Buys tab is the **right place to make track 2 explicit as an immutable purchase ledger** — and the Excel makes one architectural assertion worth importing: **track 2's all-in cost formula uses the actual paid book cost (IC) but still uses the carried-over estimated List Target to compute referral fee** — i.e. confirmed cost does not require a confirmed list price.

Two high-value lessons the Excel surfaces that shape the Confirmed Buys design:

1. **The realized-profit cost basis is defined differently in the Excel than in the app — and the app's definition is the more defensible one.** Excel's post-sale formula (`JD = IC + JB + B5`) treats `IC` as raw book price, with tax and shipping as separate estimates that fall away at sale time. The app stores `buy_cost` as one user-entered total (book + tax + shipping), so nothing "drops" at sale time — it records what was actually paid. The two compute different things from different inputs; neither is a bug. The **one real gap** is capturing the *actual* Amazon fee at sale time (Excel's `JB`) versus the app's current estimated fee model — already correctly scoped to deferred SP-API Finances work plus Estimated/Reconciled tagging.
2. **Operating fees are a separate, periodic accounting layer.** The Excel's `Totals` sheet enumerates eight account-level fee categories (LTSF, storage, removal, inbound placement, transportation, subscription, refunds, reimbursements) that are **not per-unit** and don't belong inside any individual row's profit math. The app has no surface for these today; they're deferred to a separate `[P2]` card.

The schema lands on a **parent + child** model: `confirmed_buys` (one row per buy event with `quantity_purchased`) and `confirmed_buy_units` (lazy child rows created only when SKU arrives — no null-SKU placeholders). Settings values that affect per-unit math are **snapshotted at confirm time** (currently just `prep_fee_at_purchase`), so Settings changes are forward-looking events and never retroactively rewrite history.

Everything else in the Excel — formulas, hidden sheets, the `Sorting` sheet's 1,266 columns of Keepa intake — is either already in the app at higher fidelity, or genuinely outdated and skippable.

---

## 1. What the Excel Actually Contains

Six sheets. Only `Absolute`, `Raw Calc Filter`, `Sorting`, `Totals`, and `FilterConfig` carry signal. `Temp` is explicitly marked as unused.

| Sheet | Role | Status vs current app |
| :--- | :--- | :--- |
| `Absolute` | Settings/constants (Prep Fee, Shipping, Tax, Markup) + a long worked-example note explaining the new three-track logic in plain English | Replaced — settings live in app's `settings.json` |
| `Raw Calc Filter` | 1,270-column Keepa intake sheet. Holds the live formulas for the three tracks. | Replaced by `deals` table + processing pipeline |
| `Sorting` | 1,266-column post-filter view. Same column structure as Raw Calc Filter, no row data in this copy. | Replaced by Dashboard + filter logic |
| `FilterConfig` | 10 rows mapping filter columns to operator + dropdown options (Percent_Down, Drops, Used Offer Count, Profit, Margin) | Replaced by Dashboard filter panel |
| `Totals` | Account-level periodic fee/expense ledger | **Not replaced — gap.** |
| `Temp` | Empty scratch | Skip |

The Excel is a template — the formulas exist but no real book data was ever populated. The single example value lives in the `Absolute` sheet's worked-example notes (cells D23–E44), used to walk through how a $20.03 book becomes a $133.81 list at a $111.51 manufacturer's list price.

---

## 2. The Three-Track Row Architecture (Verified)

This is the structural lesson worth carrying forward.

### Track 1 — Pre-purchase Estimated (cols HN–HQ on Sorting sheet)

| Col | Header | Formula | App equivalent |
| :--- | :--- | :--- | :--- |
| HN | List_Price | `=EI * (1 + B9)` — Keepa peak × 20% markup | Dashboard `List_at` (calculated via Mode of inferred peak-season sales, then Amazon ceiling, then AI check — much higher fidelity) |
| HO | All_in_Cost | `=ED + (ED*B7) + B6 + Q + B5 + (EI * (1+B9) * R)` — used current price + tax + shipping + FBA fee + prep + referral on projected list | Dashboard `All_in_Cost` (same formula family, slightly different ordering — note Excel folds referral into all-in cost; the app explicitly excludes it from all-in and applies it in `Profit` math) |
| HP | Profit | `=HN − HO` | Dashboard `Profit` |
| HQ | Margin | `=HP / HN` | Dashboard `Margin` |

### Track 2 — Post-purchase Actual (cols IC–IH on Sorting sheet)

| Col | Header | Formula | App equivalent |
| :--- | :--- | :--- | :--- |
| IC | Book_Cost | manual entry | `inventory_ledger.buy_cost` when `buy_cost_confirmed = TRUE` |
| ID | All_in_Cost | `=IC + Q + B5 + (IB * R)` — **actual book cost** + FBA fee + prep + referral × **carried-over estimated list target** | Computed in `/api/tracking/potential` PATCH endpoint with same logic family but using `Shipping_Included` flag |
| IE | List_Price | manual entry — user-specified actual listing price | No app equivalent yet (the app's profit math always uses the dashboard's calculated `List_at`) |
| IF | Min_Price | `=ID + (ID * B10)` — min sustainable list at 10% markup over all-in cost | No app equivalent yet; partial overlap with backend `calculate_all_in_cost` outputs |
| IG | Profit | `=IE − ID` — manually-set list minus actual all-in | Computed against system `List_at`, not user-set |
| IH | Margin | `=(IE − ID) / IE` | Same |

**Key insight from ID's formula:** the Excel intentionally **decouples confirmed cost from confirmed list price**. The user can save a confirmed `Book_Cost` (IC) while leaving `List_Price` (IE) as the system estimate (`IB` = List_Target carried over from HN). This is exactly the prep-warehouse reality where SKU and final list price arrive 1–2 months after purchase but the buy cost is known at the moment of purchase.

### Track 3 — Post-sale Realized (cols IY–JF on Sorting sheet)

| Col | Header | Formula | App equivalent |
| :--- | :--- | :--- | :--- |
| IY | Sold_Date | manual entry | `sales_ledger.sale_date` (from SP-API Orders) |
| IZ | Days_to_Sale | `=DAYS(IY, II)` — sold date minus purchase date | Not computed; would be cheap to add |
| JA | Actual_Sale_Price | manual entry | `sales_ledger.sale_price` |
| JB | Actual_AMZ_Fee | manual entry | **Not captured** (the $0.00 fees issue — would require Finances API) |
| JC | Amazon_Payout | manual entry — what Amazon actually deposits after fees | Not captured |
| JD | Aall_in_Cost | `=IC + JB + B5` — **actual paid book cost + actual AMZ fee + prep, period** | Currently computed by reusing the projected `calculate_all_in_cost` (see `2026-05-23_Diagnose_Sales_Profit_Tab.md`) |
| JE | Net_Profit | `=JC − JD` — Amazon payout minus realized all-in | Currently `realized_sale_price − buy_cost − estimated_fees` |
| JF | Profit_Margin | `=JE / JD` | Same |

**Two architectural deltas vs the current app:**

1. **JD's cost basis differs from the app's by definition, not by error.** The Excel treats `IC` as the raw book price, with tax (B7) and shipping (B6) as separate estimated line items baked into the *projected* all-in cost (HO/ID) that then fall away at sale time — leaving `JD = raw book + actual fee + prep`. The app stores `buy_cost` as a single user-entered total (book + tax + shipping; see §8 Q1 resolution). Tax and shipping don't "drop" at sale time in the app because they were never separate — they're part of the persisted paid total. **The two formulas compute different things from different inputs; neither is wrong.** The app's approach is in fact the more defensible: it records what the user actually paid rather than re-deriving acquisition cost from estimates at sale time. There is no cost-basis "drift" to fix here, and no task should be created to chase one.

2. **JE uses Amazon Payout, not Sale Price.** This is the cleanest representation of realized profit: take what Amazon actually deposited, subtract what you actually paid out. The one genuine gap the Excel surfaces is `JB` — the **actual** Amazon fee at sale time — versus the app's current **estimated** fee model. That gap is already correctly scoped: SP-API Finances integration (deferred) plus the "Estimated vs Reconciled" tagging from `Tracking_UX_Audit.md`. Nothing further to add. Until Finances lands, realized profit stays explicitly tagged Estimated.

### What Confirmed Buys gets from this architecture

The fourth tab should own track 2 explicitly as the **immutable purchase ledger**. Concretely:

- **IC equivalent (`book_cost_paid`)**: the raw price the user paid the supplier. Editable inline at confirm time. Sets a `book_cost_paid_confirmed_at` timestamp.
- **purchase-date stamp (`purchase_date`)**: when the buy happened. Required at confirm time.
- **Prep fee, tax rate, shipping cost snapshots**: copied from current `settings.json` at confirm time and stored on the row, so future settings changes don't retroactively re-warp historical purchase math. (The Excel handles this by being a frozen template; the app needs an explicit snapshot.)
- **SKU and final list price**: optional at confirm time, fillable later via reconciliation. The Excel's design — IC confirmed without IE — is the right precedent.
- **All downstream tracks (Active Inventory, Sales & Profit) read from Confirmed Buys for cost basis.** This is the structural fix to the collision the briefing identifies: SP-API sync writes to Active Inventory; manual confirms write to Confirmed Buys; reconciliation links them via ASIN+SKU.

---

## 3. Fee Categories the App Is Missing

The Excel's `Totals` sheet lists the following account-level fees and adjustments (cells A5–A14). All eight categories below are absent from the current app's profit calculation:

| Excel category | Nature | Frequency | Where it belongs |
| :--- | :--- | :--- | :--- |
| FBA Long-Term Storage Fee | Charge per unit per month for inventory aged 271+ days | Monthly per-unit | Per-row aging adjustment OR account-level monthly summary |
| FBA Inventory Storage Fee | Monthly cubic-foot storage charge | Monthly per-unit | Same as above |
| FBA Removal Order: Return Fee | Per-unit charge when you have Amazon ship inventory back to you | Per event | Account-level event log |
| FBA Inbound Placement Service Fee | Per-unit charge for inbound shipment distribution | Per shipment per unit | Per-row at inbound time |
| Inbound Transportation Charge | Cost of shipping inventory to Amazon (Amazon Partnered Carrier) | Per shipment | Per-row at inbound time OR shipment-level |
| Subscription Fee | $39.99/month Pro Seller flat fee | Monthly account-level | Account-level periodic |
| Refund | Customer refund deduction from payout | Per event | Per-row reconciliation (links to original sale) |
| FBA Inventory Reimbursement | Credit for lost/damaged inventory | Per event | Per-row reconciliation (links to original buy or sale) |

**Implication:** these are **not** the kind of fees that belong inline on a Confirmed Buys row at purchase time. They appear weeks/months later. Some are per-unit (LTSF, storage), some are per-shipment (inbound placement, transportation), some are per-event (removals, refunds, reimbursements), one is flat account-level (subscription).

**Decision:** capture all eight categories in a single deferred card: `[P2] Capture realized Amazon fee categories for accurate Sales & Profit`. The Excel `Totals` sheet column list is that card's spec. Scope inside Confirmed Buys is **only** what was paid out-of-pocket at purchase time (book cost, tax, shipping baked into `buy_cost_paid`, plus snapshotted prep fee). Everything else is realized fee accounting and lives on the sale-side surface, blocked behind SP-API Finances integration.

This keeps Confirmed Buys focused. Folding any of the eight into the buy event would balloon the schema 3–5x and conflate two distinct accounting concerns (what was paid to acquire vs. what was paid to Amazon over the unit's lifetime).

---

## 4. Settings the App Already Has — But Worth Verifying Snapshot Behavior

From `Absolute` sheet rows 5–10:

| Excel setting | Value | App location |
| :--- | :--- | :--- |
| Prep Fee | 2.5 | `settings.json` — Prep Fee |
| Estimated Shipping | 2 | `settings.json` — Estimated Shipping (now $3.99 per `2026-05-23_Diagnose_Sales_Profit_Tab.md`) |
| Estimated Tax | 0.05 | `settings.json` — Estimated Tax |
| Increase Avg. List by | 0.1 | `settings.json` — markup |
| Default Min Price Markup | 0.1 | `settings.json` — min markup |

These are all account-level settings. The app reads them at calculation time. The Excel's hidden assumption is that they don't change between purchase and sale — which is why HO uses them once and is done.

**Decision: per-unit Settings values snapshot onto the row at confirm time.** A Settings change is a real-world event, not a correction. If the prep house switches on March 15 from $2.50 to $3.10, a book bought March 14 genuinely cost $2.50 to prep — recomputing March 14's profit using March 16's value would be factually wrong. The dev log `2026-05-23_Diagnose_Sales_Profit_Tab.md` describes the current behaviour as "historical cost settings are effectively 'baked in'" because `buy_cost` is stored as raw paid; this lesson extends to prep fee, which must also be snapshotted explicitly rather than baked-in-by-accident.

**Specifically for Confirmed Buys v1:** snapshot `prep_fee_at_purchase` from `Settings.prep_fee` at confirm time. Display-time profit calculations use this snapshotted value, not current Settings. The list of values to snapshot is small and worth being explicit about in the research card — currently just prep fee (tax and shipping are already captured raw inside `buy_cost_paid`; markup and min-price markup don't affect realized profit). Aligns with the existing backlog card `[P1] Snapshot Pass-2 Financial Metrics into inventory_ledger at Flag-Time` (same architectural pattern: history must survive Settings changes).

**Out of scope for this card, but flag in research:** monthly operating expenses (Pro Seller subscription, software, VA, internet, etc.) are a separate category from per-unit prep fee. They're per-period, not per-unit. The right model is an operating expenses table with `effective_from` / `effective_until` columns; profit calculations for a given window join against expenses whose validity overlaps the window. Existing backlog card `[P2] Add monthly expenses to Settings page` is the home for this; expand its scope to include the effective-dated structure. **Do not bundle into Confirmed Buys.**

---

## 5. What to Skip from the Excel

- **The `Sorting` and `Raw Calc Filter` sheets' 1,200+ Keepa intake columns.** The pipeline (`_process_single_deal`, `infer_sale_events`, `stable_calculations.py`) does this at far higher fidelity than the Excel's column-based calculation. Nothing to import.
- **The Wilson Score / seller-quality math.** Already in `stable_calculations.py`.
- **The "Increase Avg. List by 0.1" markup heuristic** as the way to derive list price. The app's inferred-sale Mode logic replaced this entirely; do not regress to a flat percentage markup.
- **The Used 90d/365d fallback logic** implied by Excel's reliance on Keepa stats columns. Per `INFERRED_PRICE_LOGIC.md`, these were explicitly removed in March 2026 and must not return.
- **The `Temp` sheet.** Marked as ignorable.
- **The `Absolute!$B$12` Check Restriction URL.** App uses SP-API `getListingsRestrictions` instead, which is condition-aware and per-user.
- **The hyperlink helper columns (HV–HX).** App handles these via `tracking-link` CSS class with proper deep links (per `2026-05-25_Hyperlinks_Sort_Arrows_Tracking_Page.md`).
- **The Excel's `Status` column reference in the original briefing** — I could not locate a Status column on the `Sorting` sheet header rows. If it exists, it's not in the visible header block (rows 1–3) for the column ranges examined. May have been an earlier-version artifact or held in a hidden column. Not a gap worth chasing — the app's `inventory_ledger.status` field handles this concept.

---

## 6. Recommendations Specific to the Confirmed Buys Tab

### Schema (what to add)

Two new tables — **parent + child** to match the real data lifecycle (buy events are known at confirm time; per-unit SKUs arrive 1–2 months later from the prep house).

**Parent: `confirmed_buys`** — one row per buy event. The immutable purchase ledger.

- `id` (PK)
- `asin`, `condition` (carried over from the deal at confirm time)
- `buy_cost_paid` — raw total paid (book + tax + shipping). Editable post-sale with a soft warning. Does **not** include prep fee or Amazon's fees.
- `purchase_date` (required at confirm time)
- `quantity_purchased` (integer; defaults to 1)
- `actual_list_price` (optional; fillable when known)
- **Snapshotted at confirm time, immutable thereafter:** `prep_fee_at_purchase` (from `Settings.prep_fee`). Currently the only Settings value needing snapshot; explicitly enumerated in the research card so future Settings additions are evaluated against this list.
- `created_at`, `confirmed_at`
- Cross-references: `source_deal_id` (link to the `deals` row at confirm time, survives that row rotating out)

> **Sequencing note — snapshot field overlap.** `source_deal_id` and `prep_fee_at_purchase` overlap with the backlog card `[P1] Snapshot Pass-2 Financial Metrics into inventory_ledger at Flag-Time`. If that card ships first, snapshot fields may already exist on the row that becomes the confirm source. Sequence the two cards and reconcile their snapshot fields so the system ends up with **one** snapshot mechanism, not two parallel ones. Decide which card owns the canonical snapshot write before either is implemented.

**Display-time computation** (do not store): `all_in_cost = buy_cost_paid + prep_fee_at_purchase`. Amazon fees (FBA + referral) apply against sale revenue, not against the buy.

**Child: `confirmed_buy_units`** — one row per unit, created **lazily**. No null-SKU placeholders.

- `id` (PK)
- `confirmed_buy_id` (FK to parent)
- `sku` (required at row creation — the row's existence is what indicates a SKU has been assigned)
- `linked_inventory_ledger_id` (nullable; populated when Amazon shows the unit at FBA)
- `linked_sales_ledger_id` (nullable; populated when reconciliation matches a sale)
- `created_at`

**Trigger points for child row creation** (both supported):
1. SP-API sync sees a SKU it can match to a `confirmed_buys` row (via ASIN + purchase_date proximity) → create child row
2. User manually enters a SKU on the Confirmed Buys row → create child row

**Reconciliation query pattern:** for any parent row with `quantity_purchased = N`, expand to N virtual units and left-join against `confirmed_buy_units`. Missing child rows mean "SKU not yet assigned" — meaningful state, not a bug. This is how the "I confirmed 5 of this SKU but Amazon only shows 3" surface gets built.

### Behaviour

- **Confirm flow rewrite:** "Confirm" on Potential Buys writes a row to `confirmed_buys` (not `inventory_ledger`). SKU not required at confirm time. Sets `purchase_date`. Snapshots `prep_fee_at_purchase`. No child rows created yet.
- **SP-API sync stays on `inventory_ledger`** — that table becomes Amazon's authoritative view, decoupled from the user's purchase ledger.
- **Reconciliation engine** (drafted in `[P1] Tracking UX — 3 of 3`): match `confirmed_buys` rows to `inventory_ledger` rows via ASIN + condition + purchase_date proximity; create `confirmed_buy_units` child rows when SKU matches succeed; surface mismatches ("confirmed 5, Amazon shows 3") as a reconciliation queue.
- **Cost basis for Sales & Profit:** FIFO match targets `confirmed_buy_units` (one unit per child row) → `confirmed_buys.buy_cost_paid + prep_fee_at_purchase` for cost basis. Stable across Settings changes because prep fee is snapshotted, not recomputed.
- **Edit policy on `buy_cost_paid`:** soft confirmation dialog on sold rows ("This item has been sold. Editing will recalculate realized profit. Continue?"). One click to dismiss. Recalculation flows through to Sales & Profit. No hard lock — solo-seller workflow needs a fix path for transcription errors, wrong tax, forgotten shipping.

### What to defer (do not absorb into Confirmed Buys)

- **The eight `Totals` sheet fee categories** — realized post-sale fees, unrelated to capturing what was paid at purchase. Separate card: `[P2] Capture realized Amazon fee categories for accurate Sales & Profit`. The Excel `Totals` column list becomes that card's spec.
- **A "true Amazon payout" column** — blocked on Finances API integration. Until then, Sales & Profit's realized profit stays explicitly tagged as Estimated (per `Tracking_UX_Audit.md` recommendation).
- **`actual_list_price` as a required input** — keep it optional. The Excel design supports IC-without-IE; the app should too.
- **Monthly operating expenses (subscription, software, VA, etc.)** — different category (per-period, not per-unit). Handled by expanding the existing `[P2] Add monthly expenses to Settings page` card to include an effective-dated structure (`effective_from` / `effective_until` columns; profit calcs join expenses overlapping the calculation window).
- **Per-period prep fee** (tiered pricing if/when prep house pricing becomes more complex) — `prep_fee_at_purchase` snapshot is sufficient for v1's flat-rate case. Future migration to effective-dated prep fee is straightforward and already noted in backlog card `[P1] Capture actual costs and SKU at Confirm step`.

### One-line failure mode for this design

The main risk is **double-write drift**: if SP-API sync ever writes to `confirmed_buys` (it should not, by design), or if a manual confirm leaks into `inventory_ledger` (the current behaviour, to be removed), the two tables diverge silently and reconciliation becomes the only signal that anything is wrong. Mitigation: enforce at the DB and code level that each table has exactly one writer (manual UI for `confirmed_buys`; SP-API sync for `inventory_ledger`), and assert this in tests.

A secondary risk is **stale child-row state**: if a SKU is reassigned at Amazon (rare but possible — repackaged returns, prep-house relabel) the `confirmed_buy_units.sku` value could go out of sync with reality. Lazy creation reduces but does not eliminate this. Mitigation: SKU changes on a child row should be allowed (with a soft warning, same pattern as `buy_cost_paid` edits), and the linked `inventory_ledger_id` / `sales_ledger_id` re-resolve on next reconciliation pass.

---

## 7. Trello Card Implications

Per the briefing, three existing cards likely change:

- **`[P1] Capture actual costs and SKU at Tracking → Confirm step`** — **absorb into Confirmed Buys design**. The relabelling and SKU-optional changes become a side effect of the new table's schema. Close this card once the Confirmed Buys research card is open.
- **`[P1] Investigate Active Inventory sync vs. manually-confirmed items behavior`** — **answered structurally by Confirmed Buys.** The fourth tab makes Active Inventory = Amazon's view and Confirmed Buys = user's view, with reconciliation linking them. Close once the architecture decision lands.
- **`[P1] Tracking UX — 3 of 3: Sales Reconciliation Engine + Profit/ROI Display`** — **rescope**, do not absorb. The reconciliation engine becomes "match Confirmed Buys → Active Inventory → Sales & Profit" rather than "match within inventory_ledger." Sessions A–D drafts likely need a small refactor to reflect the new source of truth for "what I paid," but the underlying FIFO matching and Profit/ROI display work survives intact.

Suggested new cards (in dependency order):

1. `[P1] Research — Confirmed Buys schema and data lifecycle design` (this doc feeds it)
2. `[P1] Implement — `confirmed_buys` parent table + lazy `confirmed_buy_units` child; migration; prep_fee_at_purchase snapshot; write path from Potential Buys`
3. `[P1] Implement — Confirmed Buys tab UI (read-mostly ledger view; editable `buy_cost_paid` with soft-warning-on-sold dialog; `actual_list_price` and per-unit `sku` editable inline; child rows surface as expandable detail under parent)`
4. `[P2] Reconciliation — match Confirmed Buys ↔ Active Inventory (ASIN + condition + purchase_date proximity); lazily create `confirmed_buy_units` on SKU match`
5. `[P2] Refactor — Sales & Profit FIFO source switches to `confirmed_buy_units` for cost basis`
6. `[P2] Capture realized Amazon fee categories for accurate Sales & Profit` (Excel `Totals` sheet list = spec)
7. **Existing card to expand:** `[P2] Add monthly expenses to Settings page` — add effective-dated structure (`effective_from` / `effective_until`)
8. `[P3] Future — `shipments`, `ledger_adjustments` tables, per-period prep fee tiers (sequenced after SP-API Finances integration)`

> **Board hygiene — do not let post-launch work compete with launch-blockers.** Cards 1–3 (research + two implementation) are the launch-blocking core; the tab is usable once they ship. Cards 4–8 are post-launch and should **stay out of "To Do"** until the core three are done. Reconciliation, realized-fee capture, and the monthly-expenses expansion are all valuable but none of them block a usable Confirmed Buys tab — keeping them parked prevents the board from filling with work that crowds out the launch path.

---

## 8. Resolutions and One Remaining UX Heads-up

**Resolved during research review (May 27, 2026):**

1. **`buy_cost` semantics:** raw total paid (book + tax + shipping). Excludes prep fee (Settings constant, added at display time) and Amazon's referral + pick-and-pack fees (deducted from sale revenue, not buy). For Confirmed Buys: stored as `buy_cost_paid`; no precomputed all-in column.
2. **Edit policy after sale:** soft confirmation dialog, not a hard lock. Recalculation flows through to realized profit by design — solo-seller workflow needs a fix path.
3. **Row granularity:** one row per buy event with `quantity_purchased` (parent `confirmed_buys`); per-unit data lives in lazy child `confirmed_buy_units` rows created when SKU arrives.
4. **Table names:** `confirmed_buys` + `confirmed_buy_units` (mirrors the UI label; avoids accountant-y or overly generic names).
5. **Child row creation:** lazy. No null-SKU placeholders. Triggered by either SP-API SKU match or manual SKU entry on the parent row.
6. **`Status` column from Excel:** non-issue. `inventory_ledger.status` is the equivalent concept; no separate field needed on Confirmed Buys.

**Remaining heads-up worth capturing in the research card:**

**Settings-change UX implication of the snapshot model.** With `prep_fee_at_purchase` snapshotted onto each `confirmed_buys` row at confirm time, a Settings change to `prep_fee` will *not* retroactively change historical row math — which is the correct behaviour, but the inverse of what a user might naively expect ("I changed prep fee, why didn't March's profit update?"). Worth a short helper line in the Settings UI near the prep fee field: *"Prep fee applies to buys confirmed on or after this change. Historical rows keep their original prep fee."* Trivial copy change; prevents a confused support thread later.

This is the same architectural pattern as the existing `[P1] Snapshot Pass-2 Financial Metrics into inventory_ledger at Flag-Time` card. Worth aligning the copy/UX treatment across both surfaces so the user encounters one consistent mental model: *"the system records what was true at the moment, and Settings changes are forward-looking events."*
