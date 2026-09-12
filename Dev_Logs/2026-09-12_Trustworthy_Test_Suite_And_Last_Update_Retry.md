# Dev Log Entry: Make the Test Suite Trustworthy, and Stop `last_update` Burning 10s Per Deal

**STATUS BLOCK**
- **Shipped:** PR #338 — `sys.modules` pollution removed at its source, a conftest guard so it cannot return, `FUNCTION_LIST[10]` set to `None` (the `last_update` column stays NULL by owner decision), `@retry` removed from both timestamp functions, `run_tests.sh` converted to a real gate, the stale batching test corrected, 5 docs updated.
- **Live:** merged, main at `0b9dc78`. **Needs a pull + `deploy_update.sh`** — two production files changed. No schema change, no migration, no new runtime dependency.
- **Measured:** suite **97 passed / 26 failed → 135 passed / 0 failed**. `FUNCTION_LIST` wall clock **10.00s → 0.00s**. Every module now gives identical results run alone and in-suite, verified ID by ID across all 135.
- **User-visible:** nothing on screen. Heavy path recovers **10 seconds per newly discovered deal**. The `last_update` column was NULL and stays NULL.
- **Reversed in review:** my round-1 fix made `last_update` write. Tim rejected it — wrong format, wrong coverage, wrong path. See §3.3 before refilling that slot.
- **Corrections to `2026-09-11b`:** `run_tests.sh` **did** exit non-zero; what it could not do was see cross-module interference. And 25 of the 26 failures were pollution, not 26.
- **I was wrong in the PR body too:** "Nothing here runs in production" is false — see §6.
- **Next:** open item 2 from `2026-09-11b` — the pricing inference fix — is now unblocked.

**Date:** September 12, 2026
**Files:** see §9
**Status:** SUCCESS — MERGED TO MAIN (PR #338). This entry is the docs-only follow-up.

---

## 1. Task Overview

Open item 1 from `Dev_Logs/2026-09-11b_Remove_1yr_Avg_Listing_Average_Fallback.md`, owner-set as the precondition for the pricing-inference work. Two defects, both already diagnosed in that log's §8, so the job was to verify each against source and fix it — not to re-derive it. Both verified as stated, with the three corrections in §2.

Scope was explicitly tight: no pricing, inference, or dashboard changes. It held.

Two rounds. Round 1 shipped both fixes and asked four questions. Tim answered all four, reversed one of my decisions, and approved three changes I had flagged but not made. Round 2 shipped those.

---

## 2. Premises That Turned Out Wrong

**(a) "`run_tests.sh` cannot gate anything today."** — the brief, carrying forward `2026-09-11b` §7. **Wrong as written. It did exit non-zero.** Ran it on the parent commit: exit code 1. The mechanism is explicit — `run_tests.sh:18-20` on `c1ade77^` is `if [ $? -ne 0 ]; then echo "FAILED: $mod"; exit 1; fi`.

What it actually could not do is see the defect. `run_tests.sh:5` was `find tests -maxdepth 1 -name "test_*.py"` and `:17` ran `python3 -m unittest "$mod"` — **one module per process**. Cross-module interference cannot occur in that shape, and no conftest is ever loaded, so a green run said nothing about the in-suite result. It also stopped at the first failing module, which is why the dev log's own baseline numbers came from pytest and not from it. The distinction matters: "make it fail" was already true; "make it able to see this" was the real work.

**(b) "That is the cause of all 26 pre-existing failures."** — `2026-09-11b` §8. **25, not 26.** Ran each of the 8 failing modules alone: seven were fully green alone, and `test_smart_ingestor_batching` was **1 failed / 2 passed** — so 2 of its 3 were pollution and 1 was a genuine pre-existing failure. That one was stale (§3.7) and is fixed here.

**(c) "You should see roughly 94 passed / 26 failed."** — the brief. Actual **97 / 26**. The extra 3 are the tests PR #337 added on top of the run the estimate came from. Not a defect, recorded so the next baseline is not read as drift.

Everything else in §8 checked out exactly as written, including the 10-second figure, the line numbers, and the `last_price_change` sibling diagnosis.

---

## 3. Hypotheses Raised and Discarded

**3.1 "Scope the mocking with `patch.dict` or a fixture instead of removing it."** REJECTED, and this is the one worth reading. The brief offered it as an option and it does not work. `patch.dict(sys.modules, ...)` would restore the five mocks, but `test_approve_dedup.py` imports `wsgi_handler` **while they are live**, so `sys.modules['wsgi_handler']` is left holding a module whose `app` is a MagicMock — a sixth polluted entry the patch does not cover. Three other modules import `wsgi_handler` for real (`test_auth_phase1.py:8`, `test_dashboard_filtering.py:10`, `test_deduplication.py:13`) and get that one. Containing five mocks while manufacturing a sixth artefact is not a fix.

**3.2 "Use `tests/_real_module.load()` in the affected modules."** REJECTED. That is the sidestep PR #336 already used and deliberately documented as a sidestep (`tests/_real_module.py` docstring). It repairs consumers one at a time and leaves the producer live, so the next module added to the suite inherits the problem.

**3.3 "Make `last_update` run, by giving `logger_param` a default."** **SHIPPED IN ROUND 1, REVERSED BY OWNER IN ROUND 2.** Do not reinstate it. Three reasons, and only the first was mine:

1. Through the generic loop only **1 of the 3 sources** `AGENTS.md` §7.3 documents is reachable. `processing.py:126` calls `func(product_data)` with one positional argument, which binds the merged product dict to `deal_object` and leaves the function's own `product_data` parameter at its default — and sources 1 and 3 both read that parameter. I flagged this.
2. The generic loop is **heavy-path only** (`smart_ingestor.py:584`; `_process_lightweight_update` does not run it), so the column would be populated on newly discovered rows and NULL on light and Stale Rescue rows. A column whose meaning depends on which path last touched the row.
3. It renders **Toronto-local, space-separated** time where every other timestamp writer in the system uses **UTC isoformat**. That exact mismatch is what caused the Stale Rescue cutoff defect fixed in PR #332. I did not weigh this and should have.

Owner conclusion, now in `AGENTS.md` §7.3 and the `field_mappings.py` slot comment: *a half-populated local-time column that nothing reads is worse than a NULL one.* The lesson generalises — "the column is empty, let's fill it" is not a reason to fill it. `tests/test_field_mappings_call_contract.py::LastUpdateIsDeliberatelyUnwiredTest` pins the slot at `None` so the next agent has to read the reasons before reversing it.

**3.4 "Add `pytest` to `requirements.txt`."** REJECTED. It is installed on the VPS by the documented deploy sequence, and this is a test-only tool. `requirements-dev.txt` instead, with `run_tests.sh` failing loudly and printing the install command if pytest is missing.

**3.5 "Assert the 10-second cost by timing the call."** REJECTED as flaky. Asserting that **zero** `time.sleep` calls occur across the whole list is deterministic and says the same thing.

**3.6 "Have the guard report per-module through a failing fixture rather than aborting the run."** REJECTED for import-time pollution specifically. pytest imports every test module before running the first test, so by the time any fixture runs the damage is already done and the resulting failures land on innocent modules. Attribution has to come from the collection hooks, so a `pytest.UsageError` from `pytest_collection_modifyitems` aborts with the offending module named (exit code 4). The module-scoped fixture is kept for the *runtime* case, where per-module reporting does work (exit code 1).

**3.7 "Fix `test_smart_ingestor_batching::test_batching_logic` in round 1."** REJECTED in round 1 under `AGENTS.md` §3, flagged instead with a diagnosis; **approved by owner in round 2 and shipped.** Recorded because the process worked as designed: the test was stale, not the code, and confirming which side was wrong was cheap and read-only, but changing a test assertion to match code is an owner call. Tim's reason for approving: a gate with one permanently-red test is not a gate.

**3.8 "Also strip the `@retry` from `last_price_change` in round 1."** REJECTED in round 1 (§3, noticed in passing), approved in round 2. Confirmed zero behaviour change before touching it: the function has exactly three exits and all three are `return`, never a `raise`, so the decorator never engaged — including on the Stale Rescue path, where it returns `-` on every single call.

---

## 4. Root Cause

Two independent defects, both a **call contract nobody checked**, plus one meta-cause that hid both.

**4a. The producer/consumer contract on `sys.modules`.** `tests/test_approve_dedup.py:12-16` assigned `MagicMock()` into `sys.modules` for `flask`, `celery_app`, `keepa_deals.db_utils`, `keepa_deals.janitor` and `keepa_deals.ava_advisor` at module import time, with no teardown, and then imported `wsgi_handler` under them. pytest imports every test module before running any test, so all six artefacts were live for the whole session. 25 failures, including all 12 in `tests/test_lightweight_upsert_preservation.py` — the guard `AGENTS.md` §7.12 requires to stay green, which passed 12/12 alone.

The mocking was never necessary. flask and celery install from `requirements.txt`, and the sibling `test_deduplication.py:13` has always imported `wsgi_handler` with no mocks at all.

**4b. The `FUNCTION_LIST` call contract.** `field_mappings.py` index 10 held `stable_deals.last_update`, whose `logger_param` had no default, against a loop that passes one positional argument (`processing.py:126`). Every call raised `TypeError`. `_process_single_deal` catches per field and logs a warning, so the pipeline carried on; `upsert_deal_rows` then bound the missing key as NULL (`db_utils.py:105`, `tuple(row.get(col) for col in sanitized)` — a **missing key becomes NULL, not a `-` sentinel**, which is what made the "what is stored today" question answerable). The `@retry(stop_max_attempt_number=3, wait_fixed=5000)` turned that permanent error into two 5-second sleeps per newly discovered deal.

Audited the whole list rather than assuming: **68 non-`None` entries, and this was the only one the loop could not satisfy.** `inspect.signature` follows `retrying`'s `__wrapped__`, so the decorated entries report their real signatures and the audit is not fooled by a `(*args, **kwargs)` wrapper.

**4c. Why neither was visible.** `run_tests.sh` ran one module per process, so 4a could not occur there; and 4b cost only wall clock and a NULL column, neither of which any test or alert watched. The end-to-end tests being a flat 10.0s regardless of fixture size — `2026-09-11b` §3.5 — was the only symptom either defect ever produced, and it was found by profiling, not by reading.

---

## 5. The Fix

### 5a. Defect A — the suite poisons itself

Mocking removed at the source. `test_approve_dedup.py` imports `wsgi_handler` for real and drives the route body inside `app.test_request_context()`, so `request.form`, `session` and `url_for` are the real Flask objects rather than mock attributes. Coverage unchanged; one test added for the `logged_in` gate.

`tests/conftest.py` is the guard. It snapshots `sys.modules` around each module's import (`pytest_collectstart` / `pytest_collectreport`, which fire immediately either side of the import — verified empirically, not assumed) and around each module's tests, and fails the run naming the offender. It reports only **deltas against what that module found**, so ordinary new imports are never flagged.

Verified against all four cases: a mock installed at import time (aborts, names the module), a mock installed during a test (error at that module's teardown), a pre-existing entry replaced, a pre-existing entry deleted. A scoped `patch.dict(sys.modules, ...)` passes clean.

### 5b. Defect B — `last_update`

`FUNCTION_LIST[10]` is now `None`, index alignment preserved (247 headers, 247 slots, 67 non-`None` entries). The column stays NULL, by owner decision — §3.3. `stable_deals.last_update` is kept, since it holds the only implementation of the three-source MAX that §7.3 describes, but with its `logger_param` default and no `@retry`, so a re-wire cannot repeat the defect. `last_price_change` lost its `@retry` too (§3.8).

### 5c. The gate

`run_tests.sh` runs the whole suite in **one process** via pytest and reports every failure instead of stopping at the first. `pytest.ini` fixes the scope and excludes `tests/Legacy`, whose `test_diagnose_script.py:14` imports `diagnose_dwindling_deals` — a module no longer in the repo — so a bare `pytest` aborts the entire run on a collection error.

### 5d. Measured

| | parent `a6bcc34` | merged `0b9dc78` |
|---|---|---|
| suite | 97 passed / **26 failed** | **135 passed / 0 failed** |
| `FUNCTION_LIST` wall clock, whole list | **10.00s** | **0.00s** |
| `tests/test_field_mappings_call_contract.py` | 1 passed / **6 failed**, 31.28s | 9 passed, 1.29s |
| module result alone vs in-suite | 25 IDs differ | **135 of 135 identical** |

The 31.28s on the parent is the retry sleeps showing up directly in a test file that does nothing but call the list a few times.

---

## 6. Deployment Result

PR #338 merged; main at `0b9dc78`. Written by Tim, not by this session.

**Correction to my own PR body.** It says "Nothing here runs in production." **That is false.** `keepa_deals/field_mappings.py` and `keepa_deals/stable_deals.py` are both production modules, and `FUNCTION_LIST[10] = None` changes what the Smart Ingestor computes on every heavy-path deal — that is the whole point of the change. It needs the normal `git pull origin main` + `deploy_update.sh` to take effect. What is true, and what I should have written, is that there is **no schema change, no migration, no new runtime dependency and no data change**: the `last_update` column was NULL before and is NULL after, so no existing row is touched.

`requirements-dev.txt` is additive and only needed to run the tests. `requirements.txt` is untouched.

**Expected signal after deploy:** heavy-path deals complete roughly 10 seconds faster each. Nothing on the dashboard changes. There is no counter for this, so the honest verification is a `celery_worker.log` timing comparison on the Commit stage, or simply the absence of the two 5-second gaps per newly discovered deal.

---

## 7. Open Items

Carried from `2026-09-11b` §7, unchanged and still in priority order:

**1. The pricing inference fix — now unblocked, and next.** Price association picking the post-sale asking price; the 240-hour rank-confirmation window accepting unrelated rank drops; the IQR giving no protection at `n <= 3`. Still blocked on two owner decisions: Grok-picked sales, and minimum sale count versus a UI flag.

**2. A recovery plan for rows already carrying inflated prices.** Still the item that decides when the dashboard is trustworthy again. A fix to the inference repairs no existing row.

**3. Carried forward.** Amazon ceiling clamp and the A-10 AI-check bypass. Blank **Ago** on 893 visible rows. Expiry policy for permanently incomplete rows. The swallowed exceptions in `get_trend` and `analyze_sales_rank_trends`. `POST /api/run-janitor` auth. Fee and settings defaults. `backup_db.sh` copying a WAL database with `cp`.

New, from this session:

**4. The `last_price_change` DB column is typed `REAL` but stores a timestamp string.** Read off a schema built from `headers.json`: `last_update` is `TEXT`, `last_price_change` is `REAL`. SQLite's dynamic typing stores the string anyway so nothing is currently broken, but the declared type is wrong and any future code that trusts it will be. `last_update` is correctly `TEXT`. Not touched — out of scope, and the type is derived by `recreate_deals_table`, so "fixing" it means changing a transform that governs 248 columns.

**5. `AGENTS.md` §5.2 tells agents to use `DATABASE_URL=dev_deals.db`, which only works as a real environment variable set before the process starts.** See §8. Worth a one-line clarification in §5.2 next time that file is edited.

---

## 8. Infrastructure Findings

Facts established by reading source this session that are written down nowhere else in the repo.

**`DB_PATH` is bound at import time, from the module's own location, not the cwd.** `keepa_deals/db_utils.py:12` — `DB_PATH = os.getenv('DATABASE_URL', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db'))`. Two consequences. First, `DATABASE_URL` must be set **before `keepa_deals.db_utils` is first imported**; an `os.environ[...]` assignment or a `patch.dict` inside a test is too late, because the constant is already bound. `AGENTS.md` §5.2's `DATABASE_URL=dev_deals.db` therefore only works as a shell-level env var. Second, any code path that does not patch `DB_PATH` writes the **production filename** into the repo root regardless of where the process was started.

**Importing `wsgi_handler` does not create `deals.db`, but it does write `xai_token_state.json` into the current working directory.** The deals-table DDL sits behind `@app.before_request` (`wsgi_handler.py:2960-2969`), so it fires only on a real HTTP request — `app.test_request_context()` does not dispatch it. The token-state file is written at import. Verified by importing the module from an empty temp directory: `xai_token_state.json` appeared, `deals.db` did not.

**`product_data.update(deal)` serves BOTH ingestion paths, not just the light one.** `smart_ingestor.py:573`, above the `if asin in existing_asins_set` branch at `:576`. `2026-09-10` §2(a) cites it at `:550` as a light-path detail; it is one merge point feeding both. That is why the heavy path's `product_data` carries top-level deal keys like `lastUpdate` and `currentSince` alongside the product's own `stats` and `csv` — which is the whole basis of §3.3 reason 1.

**A low refill rate silently halves the new-deal limit.** `smart_ingestor.py:46` sets `MAX_NEW_DEALS_PER_RUN = 200`; `:339` drops it to **50** when the refill rate is under 20/min. Documented nowhere. **Stale Rescue is skipped entirely below 10/min** (`smart_ingestor.py:206-208`), which `System_Architecture.md` §3.A does not mention either.

**`clean_numeric_values` matches column names case-sensitively by substring.** `processing.py:341` — `any(k in key for k in ["Price", "Cost", "Fee", ...])`. `"last price change"` contains `price` but not `Price`, so it is **not** coerced and the timestamp string survives. The behaviour is correct; it is correct by accident of capitalisation, and a rename to `"Last Price Change"` would start casting it to float and storing NULL.

**A doc that contradicted the code, now fixed.** `System_Architecture.md` §3.A stated the peek batch "reduces to 20 if refill rate < 20/min, and to 15 if refill rate < 10/min". The code (`smart_ingestor.py:492-505`) does **1** below 10/min, **20** below 20/min, **15** below 30/min, and 50 above — so the doc was wrong in both directions, and the 15-tier it misattributed to starving accounts is the tier the live 25/min plan actually runs in. `Data_Logic.md` had two of the three right and omitted the 15-tier entirely. Both corrected in PR #338 and now guarded by `tests/test_smart_ingestor_batching.py`.

**Fresh-sandbox setup, for the next agent.** `pip install -r requirements.txt` fails on blinker ("Cannot uninstall blinker 1.7.0, RECORD file not found"). Use `pip install --ignore-installed blinker -r requirements.txt`. Without it, 26 of 30 test modules error at import on missing celery/pandas/dotenv, which looks exactly like a broken branch. Now recorded in `AGENTS.md` §6.4.

---

## 9. Files Modified

**PR #338 (merged) — round 1:**

| file | change |
|---|---|
| `tests/test_approve_dedup.py` | `sys.modules` mocking removed; route driven through `app.test_request_context()`; 1 test added |
| `tests/conftest.py` | new — the `sys.modules` pollution guard |
| `tests/test_field_mappings_call_contract.py` | new — the `FUNCTION_LIST` call contract |
| `keepa_deals/stable_deals.py` | `last_update`: `logger_param` default, `@retry` removed |
| `run_tests.sh` | one-process pytest run; fails loudly without pytest |
| `pytest.ini` | new — scope, and the `tests/Legacy` exclusion |
| `requirements-dev.txt` | new — pytest only |
| `AGENTS.md` | §7.3 and §6.4 |
| `Documentation/Data_Logic.md` | new `last_update` column entry |
| `README.md` | one line for `requirements-dev.txt` |

**PR #338 — round 2 (owner follow-ups):**

| file | change |
|---|---|
| `keepa_deals/field_mappings.py` | `FUNCTION_LIST[10] = None` with the three reasons; import commented out |
| `keepa_deals/stable_deals.py` | `last_update` comment rewritten to the decision; `@retry` removed from `last_price_change` |
| `tests/test_field_mappings_call_contract.py` | `last_update` tests reframed to pin the `None` slot; retry tests cover both functions |
| `tests/test_smart_ingestor_batching.py` | `test_batching_logic` rewritten to assert all four peek tiers |
| `AGENTS.md` | §7.3 rewritten: the column is deliberately unpopulated |
| `Documentation/Data_Logic.md` | `last_update` entry rewritten; peek batch tiers corrected |
| `Documentation/System_Architecture.md` | §3.A peek batch tiers corrected |

**This PR:**

| file | change |
|---|---|
| `Dev_Logs/2026-09-12_Trustworthy_Test_Suite_And_Last_Update_Retry.md` | this entry |
