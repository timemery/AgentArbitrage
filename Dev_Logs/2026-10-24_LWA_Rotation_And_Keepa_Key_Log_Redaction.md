# Dev Log Entry: LWA Secret Rotation, and the Keepa Key Redacted From Every Log Record (#145)

**STATUS BLOCK**
- **Shipped:** PR **#364**, merged as **`d3dca60`** (commit `f3c66a6`) on 2026-10-24. Deployed with `git pull` + `deploy_update.sh`. Trello **#145** and **#155** are closed.
- **What changed (code):** importing `keepa_api` now redacts every log record in the process where the record is created. That covers tracebacks, debug URLs and urllib3's request line. The seller fetcher no longer sends the `"Unknown"` sentinel to Keepa, and no longer passes a `None` token count to `update_after_call`. Prices are unchanged, so there is no `PRICING_LOGIC_VERSION` bump.
- **What changed (ops):** the SP-API LWA client secret was rotated after Amazon blocked the app for missing the 2026-10-22 deadline, and SP-API calls work again. The Keepa API key was rotated too. Both new values are in `.env` on the box and both were verified live.
- **Open:** next LWA rotation is due ~2027-04-22 (Trello reminder due 2027-04-08). `Keepa_Deals.py:211` was left untouched. The web process logs at DEBUG (§7).

**Date:** October 24, 2026
**Files:** see §8
**Status:** SHIPPED and live.

---

## 1. Task Overview

The session started as an ops task. Amazon's email said the LWA client secret for application `amzn1.sp.solution.b2317d23-19e3-4a8d-9c49-960b6e793d82` had to be rotated by 2026-10-22T15:19Z. The email arrived after that deadline, so the app was already blocked from SP-API. The owner rotated the secret in the portal and replaced it in `.env`. CC located where the secret is read, wrote the verification one-liner, and caught a wrong paste.

Then two cards from the board:
- **#155** (vault only, no repo change): the locked command-label standard was added to `_knowledge/Infrastructure/AA-ClaudeCode-Session-Protocol.md`, copied verbatim from `ssh-access.md`, and every command block in that protocol was labelled.
- **#145**: rotate the Keepa key, close the log-leak paths PR #347 did not cover, and stop sending `seller=Unknown` to Keepa.

## 2. Premises That Turned Out Wrong

- **"A `logging.Filter` on the handlers"** (the card's proposed fix). It was not used. Celery attaches its handlers after our modules import, so a filter added at import misses them. A filter on a *logger* does not apply to records that propagate up from child loggers. The fix wraps the **log record factory** instead (`logging.setLogRecordFactory`). Every record in the process passes through it at creation, whatever handler later writes it.
- **The card listed two leak paths. There were three.** The one it missed: `wsgi_handler.py:49` runs the root logger at **DEBUG** into `app.log`, and `/api/product/<asin>` (`wsgi_handler.py:2482-2491`) calls `fetch_product_batch` *in the web process*. urllib3 logs every request at DEBUG as `"GET /product?key=<KEY>&..."`, so every product lookup from the dashboard wrote the key to `app.log`.
- **"The secret is the only thing to change."** Correct, and confirmed: `SP_API_CLIENT_SECRET` is read only at `keepa_deals/amazon_sp_api.py:27` and `wsgi_handler.py:76`. `SP_API_AWS_SECRET_KEY` is in `.env` but **nothing in the code reads it** (a SigV4-era leftover). Refresh tokens in the `user_credentials` table are unaffected by rotating the client secret, and they kept working.

## 3. Hypotheses Raised and Discarded

- **Using `redact()`'s own pattern in the global hook.** Rejected. `_KEY_IN_URL` redacts any `key=` value. The global hook sees every log line in the process, and `stable_products.py:61-75` logs `get_stat_value: key=current, index=2`, which would become `key=<REDACTED>`. The hook uses a stricter pattern, `_SECRET_KEY_IN_TEXT`, which only matches a value of 20+ characters (a Keepa key is 64). It is pinned by `test_a_short_lookup_key_stays_readable`.
- **Changing `get_used_product_info` to return `None` instead of `"Unknown"`.** Rejected. Both processing paths write that value into `Seller` / `Seller_ID`, so changing it would change stored rows and the dashboard. The guard went into `get_seller_info_for_single_deal` instead, the one place that sends it to Keepa.
- **Automating LWA rotation via the Application Management API.** Deferred by the owner in favour of a Trello reminder. The new secret is never returned by the call. It arrives as an `APPLICATION_OAUTH_CLIENT_NEW_SECRET` notification on an **SQS queue in an AWS account**, so automation means an SQS queue, a notification subscription, AWS credentials on the box, and code that rewrites `.env` and restarts services. That is a new failure mode to save ~10 minutes twice a year.

## 4. Root Cause

- **Key leaks:** `redact()` only protects the lines that call it. `logging` renders `exc_info` tracebacks itself, after the message was redacted. urllib3 and `stable_deals.py:61` build their own lines.
- **seller=Unknown:** `get_used_product_info` returns the string `"Unknown"` when no live offer matches `stats.current[2]` (`seller_info.py`, Step 3). The string is truthy, so `if not seller_id` let it through and Keepa returned 400. That is harmless to output, because the result was `{}` either way. But on a non-JSON error body `tokens_left` is `None`, and `update_after_call` → `_sync_tokens_from_response` does `float(None)`.

## 5. The Fix

- `keepa_api.py`: `_redact_log_record` renders the message. If a 20+-char `key=` value is present, it replaces `msg` with the redacted text and clears `args`. If `exc_info` is set, it renders the traceback and stores the redacted version in `exc_text`; `Formatter.format()` uses a pre-set `exc_text` rather than re-rendering. It also redacts `stack_info`. `install_log_redaction()` is idempotent (a marker attribute on the factory) and runs at import.
- `seller_info.py`: return `{}` for `"Unknown"` before reserving tokens or calling Keepa. Call `update_after_call` only when `tokens_left is not None`.
- **Tests:** `tests/test_keepa_log_redaction_net.py`, 10 tests. 7 fail on the parent `fe37e4a`. Full suite: **455 passed** via `./run_tests.sh`.
- **Docs:** no documented behaviour affected. No doc in `Documentation/`, `AGENTS.md` or `README.md` describes redaction or the seller sentinel.

## 6. Deployment Result

- **LWA:** new secret in `.env` → `deploy_update.sh` → `refresh_sp_api_token` against the first `user_credentials` refresh token printed `OK - new secret works`.
- **Code:** `git status` on the box reported "behind by 2 commits, can be fast-forwarded" → pull → `deploy_update.sh`, which ran clean.
- **Keepa:** new key in `.env` → deploy → `get_token_status` printed `OK - tokensLeft: 110`.

## 7. Open Items and Infrastructure Findings

- **Where the SP-API app lives:** in the **Solution Provider Portal**. `sellercentral.amazon.com/sellingpartner/developerconsole` redirects to `solutionproviderportal.amazon.com`. Account: **BR - AMWPBWE0N681M_ATVPDKIKX0DER_71865 → United States**, then Apps → Develop App Console. The production app is **AgentArbitrage-Prod** (status *Draft*). **AgentArbitrage** is a separate Sandbox app, not used by the live site. The email's `.ca` links lead to an "Enroll in New Program" page; do not enroll from it.
- **Secret format check:** a client secret starts `amzn1.oa2-cs.v1.` and the client ID starts `amzn1.application-oa2-client.`. In this session the ID was pasted into the secret slot first, and a prefix check on the box caught it: `grep SP_API_CLIENT_SECRET .env | cut -c1-45`.
- **Next LWA rotation:** ~2027-04-22 (180 days). The Trello card in "Recurring / Living Documents" is due 2027-04-08 and holds the full steps. The old secret expires 7 days after rotation.
- **keepa.com requires Chrome 130+.** The owner's Mac (Catalina, Chrome 128) cannot open it; use another device.
- **Not fixed, flagged:** `wsgi_handler.py:49` runs the web process's root logger at DEBUG, so `app.log` gets every library's debug output. The key is now redacted there, but the level itself is a noise and exposure risk for other secrets. That is an owner decision.
- **Not touched:** `Keepa_Deals.py:211`, a legacy batch seller fetch with the same `update_after_call(tokens_left)` shape.
- Old `celery_worker.log` / `app.log` still contain the **previous** Keepa key and that key is now dead, so no action is needed.

## 8. Files Modified

- `keepa_deals/keepa_api.py` (record-factory redaction)
- `keepa_deals/seller_info.py` (`"Unknown"` guard, `tokens_left` guard)
- `tests/test_keepa_log_redaction_net.py` (new)
- `.env` on the box (not in the repo): `SP_API_CLIENT_SECRET`, `KEEPA_API_KEY`
- Vault, not the repo: `_knowledge/Infrastructure/AA-ClaudeCode-Session-Protocol.md` (#155)
