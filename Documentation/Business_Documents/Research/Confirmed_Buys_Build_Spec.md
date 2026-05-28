# Confirmed Buys — Locked Build Spec

**Status:** Design locked. Feeds implementation cards (not yet created).
**Source:** `Confirmed_Buys_Excel_Findings.md` §6 hardened into a build-ready spec.
**Canonical location (proposed):** `Documentation/Business_Documents/Research/Confirmed_Buys_Build_Spec.md`
**Related docs:** `Advisor_Orientation.md` (§2 financial model, §3 architecture, §4 snapshot mechanism), `Feature_Tracking.md`, `Data_Logic.md`, `System_State.md`.

This spec is the artifact implementation cards will reference. It locks: final column types, indexes, constraints; the SQLite migration approach; the Confirm-flow rewrite sequence; the relationship between the **Pass-2 Flag-Time Snapshot** card and **Confirmed Buys**; and the post-Confirm fate of the originating `inventory_ledger` row.

It does not lock the Confirmed Buys tab UI in detail — that's a separate implementation card after the schema lands.

---

## 0. Cards this spec governs

In implementation order. Cards are not created yet; this spec is the input to that step.

1. **`[P1] Snapshot Pass-2 Financial Metrics into inventory_ledger at Flag-Time`** — ships FIRST. Independent value (fixes em-dash-on-rotated-deals in Potential Buys). Sets up the snapshot fields the Confirm flow will read from.
2. **`[P1] Implement Confirmed Buys — parent + child tables, migration, Confirm-flow rewrite`** — ships SECOND. Consumes card 1's snapshot. Includes the migration, the new write path, and the deletion of the old write path.
3. **`[P1] Implement Confirmed Buys tab UI`** — ships THIRD. Read-mostly ledger view. Editable `buy_cost_paid` with soft-warning-on-sold. Optional inline `sku` and `actual_list_price`.

Cards 4–8 from findings §7 (reconciliation, fee-category capture, monthly expenses, etc.) stay in Backlog and are out of scope for this spec.

---

## 1. The snapshot-card relationship — locked

This was the one open design question from findings §6 ("Decide which card owns the canonical snapshot write before either is implemented"). Locked decision below.

### The two snapshots are PARALLEL, not overlapping

| | Flag-Time Snapshot (Card 1) | Confirm-Time Snapshot (Card 2) |
|---|---|---|
| **Trigger** | User clicks Buy on Dashboard | User clicks Confirm on Potential Buys |
| **Writes to** | `inventory_ledger` (existing Potential Buys row) | `confirmed_buys` (new row) |
| **Purpose** | Freeze *estimate inputs* so projected Profit/ROI survive the `deals` row rotating out | Freeze *cost-basis inputs* so realized profit survives Settings changes |
| **Fields** | `snapshot_list_at`, `snapshot_fba_fee`, `snapshot_referral_pct`, `snapshot_shipping_included`, `snapshot_estimated_tax`, `snapshot_estimated_shipping`, `snapshot_prep_fee` | `prep_fee_at_purchase` (and `buy_cost_paid` itself, by being entered/edited) |

### Why `snapshot_prep_fee` and `prep_fee_at_purchase` are not the same field

They are the same *number* only if Settings.prep_fee didn't change between flag-time and confirm-time. If the user flags in January (prep fee $2.50), confirms in March (prep fee $3.10 after switching prep houses):

- `inventory_ledger.snapshot_prep_fee = 2.50` (the value the January estimate used)
- `confirmed_buys.prep_fee_at_purchase = 3.10` (what the user will actually pay)

Both correct. Both needed. Do not collapse.

### The data flow at Confirm time

```
User clicks Confirm on a Potential Buys row.
  ↓
Backend reads:
  - inventory_ledger row (the flagged deal, with its flag-time snapshots)
  - current Settings.prep_fee  ← fresh read, NOT the snapshot value
  ↓
Backend writes a new confirmed_buys row:
  - asin, condition, source_deal_id          ← copied from inventory_ledger
  - buy_cost_paid                            ← copied from inventory_ledger.buy_cost_paid
                                               (user has typically edited it inline already)
  - prep_fee_at_purchase                     ← FRESH read from Settings.prep_fee
  - purchase_date                            ← supplied by Confirm action (date picker, defaults to today)
  - quantity_purchased                       ← supplied by Confirm action (defaults to 1)
  - buyer_order_id                           ← optional, supplied by Confirm action (defaults to NULL)
  - actual_list_price                        ← NULL (optional, fillable later)
  - confirmed_at = NOW()
  ↓
Backend deletes the inventory_ledger row.
  ↓
Frontend redirects user to Confirmed Buys tab (newly visible row at top).
```

**Dismiss behavior** (Potential Buys row, no Confirmed Buys row created): deletes the `inventory_ledger` row outright. No migration, no Confirmed Buys row. Existing behavior; unchanged by this card.

**Copy, don't reference.** Per Advisor Orientation §3. The `inventory_ledger` row goes away; everything `confirmed_buys` needs is on the row itself.

**`source_deal_id` is preserved as a traceability pointer.** It points at a `deals` row that may already be gone — that's fine; it's a breadcrumb, not a foreign key relied on for joins. Stored as INTEGER, no FK constraint.

---

## 2. Schema — final column types and constraints

SQLite. All timestamps stored as ISO 8601 TEXT (`YYYY-MM-DDTHH:MM:SS`), matching the existing `inventory_ledger` and `sales_ledger` convention. Monetary values stored as REAL (matching existing columns); the app already accepts the floating-point round-off cost of REAL elsewhere — switching to INTEGER cents here would introduce inconsistency for marginal gain.

### Table: `confirmed_buys`

```sql
CREATE TABLE confirmed_buys (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    asin                    TEXT    NOT NULL,
    condition               TEXT    NOT NULL,
    buy_cost_paid           REAL    NOT NULL,
    purchase_date           TEXT    NOT NULL,                          -- ISO 8601, date portion sufficient but stored as full timestamp for consistency
    quantity_purchased      INTEGER NOT NULL DEFAULT 1 CHECK (quantity_purchased > 0),
    actual_list_price       REAL,                                      -- nullable; filled later
    prep_fee_at_purchase    REAL    NOT NULL,                          -- snapshotted from Settings at confirm time
    buyer_order_id          TEXT,                                      -- optional memo: user's amazon.com Purchase Order # (NOT the Seller Central order ID)
    source_deal_id          INTEGER,                                   -- traceability pointer, no FK constraint
    confirmed_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    created_at              TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_confirmed_buys_asin              ON confirmed_buys(asin);
CREATE INDEX idx_confirmed_buys_purchase_date     ON confirmed_buys(purchase_date);
CREATE INDEX idx_confirmed_buys_asin_condition    ON confirmed_buys(asin, condition);
CREATE INDEX idx_confirmed_buys_source_deal_id    ON confirmed_buys(source_deal_id);
```

**Notes on each column:**

- `asin`, `condition`: copied from `inventory_ledger` at confirm. `condition` follows the existing app convention (numeric code 1–5 per `Data_Logic.md`).
- `buy_cost_paid`: the user's raw paid total (book + tax + shipping). Excludes prep fee and Amazon fees. Editable post-confirm via soft warning.
- `purchase_date`: required at confirm. Defaults to today in the UI, user-editable to backdate. Stored as a full ISO 8601 timestamp for consistency with sibling tables.
- `quantity_purchased`: defaults to 1. Most buys are single-unit; quantity > 1 supports the multi-unit-purchase case directly in the parent row, with child SKUs lazy.
- `actual_list_price`: nullable. The Excel design supports IC-without-IE (findings §2, Track 2). Fillable later via Confirmed Buys tab inline edit.
- `prep_fee_at_purchase`: NOT NULL. Snapshotted from `Settings.prep_fee` at confirm time. Currently the only Settings value needing snapshot here (markup and min-price markup don't affect realized profit; tax and shipping are already baked into `buy_cost_paid`). **Locked once set — never updates retroactively for that row.** Future Settings changes only affect rows confirmed after the change.
- `buyer_order_id`: nullable TEXT. Optional memo field. This is the user's **amazon.com Purchase Order #** (the order ID from their personal Amazon buyer account at the time they bought the book) — NOT to be confused with the Seller Central order ID shown on the Sales & Profit tab. Stored as TEXT to preserve any leading zeros or hyphens in the format. No calculations depend on it.
- `source_deal_id`: nullable INTEGER, no FK. Pointer for traceability only.
- `confirmed_at`, `created_at`: ISO timestamps with SQLite default. `created_at` is the row-creation time; `confirmed_at` is the same value for v1 (separate field reserved for any future case where a draft `confirmed_buys` row is created before user clicks Confirm).

**No precomputed `all_in_cost` column.** Computed at display time as `buy_cost_paid + prep_fee_at_purchase`. Matches the existing convention from `Data_Logic.md` (ROI is also dynamically computed, never stored).

### Table: `confirmed_buy_units`

```sql
CREATE TABLE confirmed_buy_units (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    confirmed_buy_id            INTEGER NOT NULL REFERENCES confirmed_buys(id) ON DELETE CASCADE,
    sku                         TEXT    NOT NULL,
    linked_inventory_ledger_id  INTEGER REFERENCES inventory_ledger(id) ON DELETE SET NULL,
    linked_sales_ledger_id      INTEGER REFERENCES sales_ledger(id) ON DELETE SET NULL,
    created_at                  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_confirmed_buy_units_confirmed_buy_id  ON confirmed_buy_units(confirmed_buy_id);
CREATE UNIQUE INDEX idx_confirmed_buy_units_sku        ON confirmed_buy_units(sku);
CREATE INDEX idx_confirmed_buy_units_inventory_link    ON confirmed_buy_units(linked_inventory_ledger_id);
CREATE INDEX idx_confirmed_buy_units_sales_link        ON confirmed_buy_units(linked_sales_ledger_id);
```

**Notes:**

- `sku UNIQUE`: a given SKU corresponds to exactly one physical unit at Amazon. Enforces this at the DB level.
- `ON DELETE CASCADE` on the parent FK: deleting a `confirmed_buys` row (rare; would be a user undo, not normal flow) removes its child units too.
- `ON DELETE SET NULL` on the inventory/sales link FKs: the child row survives even if its inventory/sales link rows are pruned. Reconciliation reruns will re-resolve the links.
- **No `condition` column** on child — inherited from parent. SKUs assigned to a `confirmed_buys` row necessarily share that buy's condition.
- **No null-SKU placeholders.** A child row exists if and only if a SKU has been assigned. Pre-SKU state is represented by `count(confirmed_buy_units WHERE confirmed_buy_id = X) < confirmed_buys.quantity_purchased`.

### What does NOT change in existing tables

- `inventory_ledger`: no schema change in this card. Card 1 (Pass-2 snapshot) is the card that adds snapshot columns to `inventory_ledger`. Confirmed Buys does not touch the table's columns; it only changes who writes to it (SP-API sync only, no more manual confirms).
- `sales_ledger`: no schema change. FIFO source switches later in card 5 (post-launch).
- `settings.json`: no change.

### Failure modes flagged for the implementation card

- **Double-write to `confirmed_buys`** would silently break the "one writer per table" rule. Mitigation: write path is `wsgi_handler.py`'s `/api/tracking/potential/<id>/confirm` endpoint **only**. SP-API sync code must not import or reference `confirmed_buys`.
- **`sku UNIQUE` violation** if two `confirmed_buys` rows somehow point at the same SKU. Should be impossible by SP-API behavior, but worth catching at the DB level rather than discovering as silent dupe-units later.

---

## 3. Migration approach

The DB has existing `inventory_ledger` rows in mixed states. Migration is one-time, irreversible (no rollback plan needed — SQLite, single user, can restore from backup if needed).

### Step 1 — back up the DB

Before any schema change, copy `instance/deals.db` to `instance/deals.db.pre-confirmed-buys.bak`. Jules task should include this as the literal first line of the script.

### Step 2 — create the two new tables

Run the `CREATE TABLE` and `CREATE INDEX` statements from §2 above. New tables are empty; no data migration into them at create time.

### Step 3 — backfill `confirmed_buys` from existing "PURCHASED"-status rows

`inventory_ledger` currently uses `status` to indicate manual purchases vs. SP-API rows. Any row that was manually confirmed (status indicates "purchased" / `buy_cost_confirmed = TRUE` and was not created by SP-API sync) needs to become a `confirmed_buys` row.

**Backfill query (logic, not literal SQL — Jules to write the script):**

For each `inventory_ledger` row where the manual-confirm signature applies (`buy_cost_confirmed = TRUE` AND the row was created by manual flow, NOT by SP-API sync — Jules to determine the discriminator from the code, likely a `source` column or its absence):

1. INSERT INTO `confirmed_buys` with:
   - `asin`, `condition`, `buy_cost_paid` ← from `inventory_ledger`
   - `purchase_date` ← from `inventory_ledger.created_at` (best available proxy; not perfectly accurate for historical rows, acceptable for backfill)
   - `quantity_purchased` ← 1 (existing rows are single-unit by current schema)
   - `actual_list_price` ← NULL
   - `prep_fee_at_purchase` ← **current `Settings.prep_fee`**. For Tim's data this is exact (prep fee has not changed in 3 years of operation; backfilled value equals what was actually paid). For any future user whose prep fee has changed since some current inventory was purchased, the backfill value would be approximate for affected rows; a migration override would be added at that point. Not a concern for v1 launch.
   - `buyer_order_id` ← NULL (not captured historically)
   - `source_deal_id` ← NULL (link not preserved on existing rows)
   - `confirmed_at`, `created_at` ← `inventory_ledger.created_at`
2. If the `inventory_ledger` row has a known SKU (from later SP-API match), INSERT a corresponding `confirmed_buy_units` row pointing at it.

**One-line failure mode:** if a future user has changed prep fee mid-inventory, backfilled `prep_fee_at_purchase` will be off by ($current − $historical) per affected unit. Migration script logs the value used so audit is possible.

### Step 4 — delete the migrated `inventory_ledger` rows

After successful backfill, DELETE the migrated rows from `inventory_ledger`. After this step, `inventory_ledger` should contain ONLY rows sourced from SP-API sync.

**Verification before delete:** Jules's script must SELECT COUNT from both tables and assert `confirmed_buys` row count equals the number of `inventory_ledger` rows about to be deleted. Abort if mismatch.

### Step 5 — verify

Spot-check: pick three migrated rows. Confirm `confirmed_buys` values match `inventory_ledger`'s deleted equivalents (book cost, ASIN, condition). Confirm Potential Buys tab still loads (now from `confirmed_buys` OR — see §4 — from a query specifically scoped to the pre-confirm state, depending on Tim's UX decision below).

**Locked UX decision** (confirmed with Tim 2026-05-28): Potential Buys tab **survives** as a separate tab post-launch. It remains the "pre-purchase wishlist" surface — flagged deals the user hasn't yet bought. Individual rows are **deleted** from Potential Buys on either:
- **Confirm** button → row data is migrated to a new `confirmed_buys` row, then the `inventory_ledger` row is deleted.
- **Dismiss** button → row is deleted outright (no migration).

Confirmed Buys is a **permanent record** — rows never leave that table once created. A book confirmed in 2026 is still on the Confirmed Buys tab indefinitely.

---

## 4. Confirm-flow rewrite sequence

This is the code path change: the existing `/api/tracking/potential/<id>/confirm` endpoint (or equivalent — Jules confirms exact name from `wsgi_handler.py`) currently flips `inventory_ledger.status` from POTENTIAL → PURCHASED. After this card it writes a new `confirmed_buys` row and deletes the old `inventory_ledger` row.

### Endpoint behavior — before vs. after

**Before:**
```
POST /api/tracking/potential/<id>/confirm
  → UPDATE inventory_ledger SET status='PURCHASED' WHERE id = <id>
  → 200 OK
```

**After:**
```
POST /api/tracking/potential/<id>/confirm
  Request body: {
    purchase_date: "2026-05-28",
    quantity_purchased: 1,
    buyer_order_id: "112-1234567-1234567"   ← optional; null/omitted if user skips
  }
  
  1. SELECT * FROM inventory_ledger WHERE id = <id> AND status = 'POTENTIAL'
     → if not found: 404
  2. SELECT prep_fee FROM settings.json (or however Settings is read in current code)
  3. INSERT INTO confirmed_buys (
       asin, condition, buy_cost_paid,
       purchase_date, quantity_purchased,
       buyer_order_id,
       prep_fee_at_purchase, source_deal_id,
       confirmed_at, created_at
     ) VALUES (
       <copied from inventory_ledger>,
       <from request body>,
       <from request body, may be NULL>,
       <fresh Settings.prep_fee read>, <inventory_ledger.source_deal_id if present, else NULL>,
       datetime('now'), datetime('now')
     )
     → capture new confirmed_buys.id
  4. DELETE FROM inventory_ledger WHERE id = <id>
  5. Return 200 OK with { confirmed_buy_id: <new id> }
  
  All four steps in a single transaction. Rollback on any failure.
```

### What the UI needs to change

- The Potential Buys row's "Confirm" button now opens a small modal (or inline form) with three fields:
  - **Purchase date** (date picker, default today)
  - **Quantity purchased** (number input, default 1, min 1)
  - **Amazon.com Purchase Order #** (text input, optional, demoted visually below the other two). Helper text: *"From your amazon.com order confirmation — not the same as the Seller Central order ID. Optional; leave blank if you don't need it."*
- On submit, calls the rewritten endpoint with all three values in the body (buyer_order_id may be null).
- On 200, optimistic UI either redirects to Confirmed Buys tab or removes the row from the Potential Buys list with a toast ("Confirmed — see Confirmed Buys tab"). Recommend the toast; redirect feels heavy-handed.

**Label discipline (locked):** the Confirmed Buys tab column header for this field MUST be "Amazon.com Purchase Order #" — never abbreviated to "Order #" or "Order ID" anywhere it could appear adjacent to the Sales & Profit tab's "Order ID" column. The two refer to different transactions (user's purchase from amazon.com vs. a customer's purchase from the user's FBA inventory) and conflating them in any UI surface will cause user confusion.

### Removing the old write path from SP-API sync code

SP-API sync code currently writes to `inventory_ledger` for Amazon-authoritative rows AND historically also touched manually-confirmed rows. Audit pass for card 2 (Jules task): grep `inventory_ledger` writes in the SP-API code path; confirm each is sourced from SP-API and NOT from a manual confirm. The discriminator (likely a `source` column value) becomes the explicit guardrail.

If a `source` column doesn't already exist on `inventory_ledger` to distinguish manual vs. SP-API writes, **add one** in this card. Default for existing rows after migration: `'sp_api'` (since manual ones have been migrated out). New SP-API writes set it explicitly. This gives the "one writer per table" rule something testable to assert on.

### Tests to add

- Calling the rewritten endpoint creates a `confirmed_buys` row AND deletes the `inventory_ledger` row, in one transaction.
- A failure mid-transaction leaves both tables untouched.
- After confirm, the `inventory_ledger` row is no longer findable.
- After confirm, the `confirmed_buys` row exists with the right copied fields and the fresh `prep_fee_at_purchase` value.
- SP-API sync code path does not insert into `confirmed_buys` (test against a code-grep or a runtime assertion).

---

## 5. Display logic — minimum viable for v1

This locks the read-side patterns. Full UI is card 3.

### All-in cost computation (display-time, not stored)

```python
def all_in_cost(confirmed_buy_row):
    return confirmed_buy_row.buy_cost_paid + confirmed_buy_row.prep_fee_at_purchase
```

Single function. Reused everywhere all-in cost is shown. Lives next to existing `business_calculations.py` logic — extend that module, don't create a new one.

### Projected profit, margin, ROI (pre-sale)

Same formulas as `Data_Logic.md` §6, with the cost basis swapped:

```
list_price_for_calc = COALESCE(confirmed_buys.actual_list_price, <list_at from source_deal_id if available, else fall back to flag-time snapshot>)
amz_fees = estimated_fba_fee + (list_price_for_calc × referral_fee_pct)
projected_profit = list_price_for_calc − all_in_cost(row) − amz_fees
margin = projected_profit / list_price_for_calc
roi = projected_profit / all_in_cost(row)
```

**Where the list price comes from when `actual_list_price` is NULL:** in priority order:
1. `confirmed_buys.actual_list_price` if set
2. The `deals` row at `source_deal_id` if still present
3. The flag-time `snapshot_list_at` from the *former* `inventory_ledger` row — but that row is now deleted. **Gap flagged.**

**Resolution of the gap:** the flag-time snapshot values must be copied onto `confirmed_buys` at confirm time, OR the Pass-2 snapshot card needs to write its snapshot fields onto a persistent surface that survives the Confirmed Buys transition.

**Locked decision:** copy them. Add the following fields to `confirmed_buys` to carry the flag-time snapshot forward (sourced at confirm time from the `inventory_ledger` row about to be deleted):

```sql
-- Add to confirmed_buys schema:
    snapshot_list_at         REAL,    -- copied from inventory_ledger.snapshot_list_at
    snapshot_fba_fee         REAL,    -- copied from inventory_ledger.snapshot_fba_fee
    snapshot_referral_pct    REAL,    -- copied from inventory_ledger.snapshot_referral_pct
```

These are nullable because the Pass-2 snapshot card might not have shipped yet for some pre-existing rows, or backfilled rows might not have snapshots. When NULL, fall back to live `deals` row lookup; when both are unavailable, display em-dash for projected profit/margin/ROI (acceptable degraded state; book has been purchased so the user can still see what they paid).

This is the **only material change** to the §2 schema relative to findings §6 — and it's a direct consequence of "copy, don't reference" applied to the flag-time snapshot. Worth calling out so the implementation doesn't miss it.

### Realized profit (post-sale)

Out of scope for this card. Card 5 (`[P2] Refactor — Sales & Profit FIFO source switches to confirmed_buy_units`) is where this lands. v1 Confirmed Buys shows projected math only; once a `confirmed_buy_units` row is linked to a `sales_ledger` row, the existing Sales & Profit tab handles realized display.

---

## 6. Settings UX implication (carried over from findings §8)

Add a helper line to the Settings page near the prep fee field:

> *"Prep fee applies to buys confirmed on or after this change. Historical rows keep their original prep fee."*

Trivial copy change. Belongs in card 2's UI scope (same card that does the Confirm endpoint), not a separate card. Prevents the inevitable "I changed prep fee, why didn't March's profit update?" support thread.

---

## 7. Sequencing & dependencies — locked

```
Card 1 [P1] Pass-2 Flag-Time Snapshot
   ├─ writes new columns onto inventory_ledger
   ├─ independent value: fixes em-dash on rotated-deal Potential Buys rows
   └─ MUST ship before Card 2 (Card 2 copies these values onto confirmed_buys at confirm time)
        ↓
Card 2 [P1] Confirmed Buys schema + migration + Confirm-flow rewrite
   ├─ creates confirmed_buys + confirmed_buy_units tables
   ├─ migrates manual-purchased inventory_ledger rows into confirmed_buys
   ├─ rewrites /api/tracking/potential/<id>/confirm endpoint
   ├─ adds (or confirms) a source column on inventory_ledger to enforce "one writer per table"
   ├─ adds Settings UX helper copy near prep fee
   └─ tab UI not yet — Confirmed Buys tab is empty/hidden after this card
        ↓
Card 3 [P1] Confirmed Buys tab UI
   ├─ read-mostly ledger view
   ├─ editable buy_cost_paid (soft warning on sold rows)
   ├─ inline actual_list_price and sku editing
   ├─ child rows expand under parent
   └─ shared styling/pagination with Dashboard + other Tracking tabs
        ↓
   [LAUNCH]
        ↓
Card 4+ — post-launch (reconciliation, realized fees, monthly expenses, etc.) per findings §7
```

**Card 2 should not ship without Card 1.** If Card 1 slips, Card 2's "copy snapshot values" step has nothing to copy and the Confirmed Buys row will rely on `deals`-row lookup only — usable but degraded. Acceptable as a contingency, but not the target sequence.

**Card 3 should not ship without Card 2.** A UI on no data is wasted work.

**Card 3 confirms with Tim before being written** on the open UX question from §3 step 5 (does Potential Buys remain a separate tab post-Confirmed-Buys?).

---

## 8. Out of scope (explicit)

For visibility, the following are NOT part of any of cards 1–3 and stay in Backlog:

- Reconciliation engine matching `confirmed_buys` ↔ `inventory_ledger` (card 4)
- FIFO source switch in Sales & Profit (card 5)
- Per-unit realized Amazon fee capture (card 6, blocked on SP-API Finances API)
- Monthly expenses with effective-dating (existing P2 card, expanded)
- Per-period prep fee tiers (P3)
- `shipments`, `ledger_adjustments` tables (P3)
- **Active Inventory ↔ Confirmed Buys cross-reference / status flag** — future card idea, not yet created. Concept: surface a status badge on each Confirmed Buys row showing whether the matching unit is currently listed at Amazon, aged, returned, sold, etc., pulled from Active Inventory's SP-API data. Useful but not launch-blocking; explicitly deferred to keep v1 scope manageable.
- **Auto-sync of `buyer_order_id` from amazon.com** — no official API exists. Manual entry only.

---

## 9. Decisions locked in conversation (2026-05-28)

The two open items from the original draft are resolved:

1. **Potential Buys tab survives** as a separate tab. Pre-purchase wishlist surface, distinct from post-purchase Confirmed Buys ledger. Rows deleted on Confirm or Dismiss (see §1 data flow).
2. **Prep-fee backfill uses current Settings value**, which equals Tim's actual historical prep fee (unchanged in 3 years of operation). Backfilled value is exact, not approximate, for v1's user. For any future user with a changed prep fee, a migration override would be added at that point.

Additional decisions locked in the same conversation:

3. **`buyer_order_id` added** as an optional TEXT memo field on `confirmed_buys`. Captures the user's amazon.com Purchase Order # (NOT the Seller Central order ID). No calculations depend on it. UI labels it explicitly as "Amazon.com Purchase Order #" everywhere it appears, never abbreviated.
4. **Auto-syncing buyer_order_id from amazon.com is OUT.** No official Amazon API exists for buyer-side order history. Unofficial scrapers exist (e.g. `amazon-orders` PyPI package) but require user credentials, violate Amazon TOS, and are brittle. Field is manual-entry only.
5. **Active Inventory ↔ Confirmed Buys cross-referencing is OUT of v1.** The two tables are independent ledgers in v1: Confirmed Buys = what the user bought; Active Inventory = what Amazon's SP-API reports. Future feature idea (parked, not yet a card): a status flag on Confirmed Buys rows showing aged/returned/sold/listed state pulled from Active Inventory. Worth doing eventually; explicitly NOT in v1 to keep the launch scope manageable.

---

## 10. One-line failure mode summary

The biggest risk this design eliminates is the **dual-write collision** on `inventory_ledger`. The biggest risk it introduces is **migration data loss** if Step 4 (deletion) runs without Step 3 (backfill) having succeeded — mitigated by the row-count assertion in the migration script and by the `.bak` file from Step 1.

Secondary risk: if Card 1 ships but Card 2 doesn't ship soon after, `inventory_ledger` accumulates snapshot fields that nothing consumes yet. Cost: a few unused columns. Acceptable.
