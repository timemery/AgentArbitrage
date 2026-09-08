# Dev Log Entry: Find & Fix the xAI Cost Leak (Advisor Context Cap)

**Date:** September 8, 2026
**Files:** `keepa_deals/ava_advisor.py`, `AGENTS.md`, `Documentation/System_Architecture.md`, `Documentation/Token_Management_Strategy.md`, `Documentation/Feature_Guided_Learning_Strategies_Intelligence.md`
**Status:** SUCCESS — ROOT CAUSE CONFIRMED, ONE-FILE FIX MERGED (PR #325, `789ceed` → `203f83c`), DEPLOYED, HOURLY SPEND $11.08 → <$0.01, 7-DAY SPEND −36.6%, ADVICE QUALITY IMPROVED
**Trello:** #129 (P1) — https://trello.com/c/o9x1fxJD
**Tooling note:** Investigation and fix performed via Claude Code (web) against the GitHub sandbox. All billing and log evidence supplied by Tim from the live VPS; the agent never touched the server.

---

## 1. Task Overview

xAI spend had reached **$76.77 in August** (39.2M tokens across 35,815 requests), with September tracking at ~$20.94 in 7 days. **84% of spend was prompt tokens** — completions averaged ~4 tokens per request, meaning the money was leaving in what the system *sent*, not what came back.

The task was structured as a hard STOP-and-confirm: Phase 1 read-only investigation producing a call-site inventory, a named prime suspect and two costed fix proposals; Phase 2 to implement only after explicit approval of one specific finding. Hard constraints: Advisor/Mentor is live with a real user, no model swaps, no behavioural prompt rewrites, no bundled refactors, and no staging environment — merge → pull → deploy *is* going live, so the only genuine pre-live check is reading the diff.

---

## 2. Premise Corrections (recorded so they aren't re-derived)

The task brief carried two stated facts that did not survive contact with the code. Both are recorded here because both cost investigation time.

### A. `grok-4.3` does not exist in this codebase

The brief stated the model was `grok-4.3` and that `grep -rn "grok-4.3"` would be the fastest path to the call site. It returns nothing. **All 10 xAI call sites send the literal string `grok-4-fast-reasoning`.** There is no alias, no fallback chain, no env-var-driven model selection and no model-enumeration loop. `grok-4.3` is xAI's *billing console* label for `grok-4-fast-reasoning`.

This also resolved a live doc/code drift in the opposite direction from the one expected: **`AGENTS.md` §1 listed the locked model as `grok-4-1-fast-reasoning`** — a third string, matching neither the code nor the console. The code was right; the locked-values doc was wrong. Corrected in this PR, with an explicit note that `grok-4.3` is a billing label so a future agent does not "fix" the code to match the console.

### B. The expensive path was NOT in the ingestion pipeline

The brief asserted the leak lived in ingestion/deal-processing rather than Advisor/Mentor, reasoning from xAI spend being exactly zero Aug 13–16 and resuming Aug 18 — matching the TokenManager livelock window and the day its fixes deployed.

The correlation is real but does not discriminate. It proves *ingestion* stopped (ingestion supplies the request **volume**). Zero *total* spend across those four days also means no Advisor clicks happened in that window — which is what you would expect while heads-down diagnosing a livelock. Both stories fit the outage; only per-request size distinguishes them.

Measurement settled it. Every ingestion-path prompt was reconstructed and measured:

| Ingestion call site | Measured tokens/request |
|---|---|
| `seasonality_classifier._query_xai_for_seasonality` | **220** |
| `stable_calculations._query_xai_for_reasonableness` | **257** |
| `xai_sales_inference.query_xai_sales_inference` | **~1,821** (hard-capped at 151 history rows, `xai_sales_inference.py:138`) |

**The ingestion ceiling is ~1,821 tokens.** No ingestion call site can reach the 5,000–65,000-token band the billing showed. (The 220-token seasonality prompt measured *exactly* the 220-token baseline named in the brief — confirming that site as the cheap background traffic, and ruling it out as the leak.)

**The leak was in the Advisor path, which the brief said to deprioritize.**

---

## 3. Investigation Arc (hypotheses raised and discarded, with evidence)

Recorded deliberately so these dead ends aren't re-run.

1. **"Prime Picks Pass 2 is the strongest candidate."** DISPROVEN. `prime_picks_task.get_tiered_strategies()` (`prime_picks_task.py:26`) enforces its cap on every path — `confidence == 'High'` only, 30 per category, from a fixed 4-category allowlist. It is bounded regardless of `strategies.json` size. Measured at **~7,500 tokens/call**, fired 6×/day off the Janitor chain (`janitor.py:57`) = ~50K tokens/day. There is no fallback or error branch that loads the full file. Pass 2 was clean; the cap was real, enforced, and on the wrong function.

2. **"The seasonality classifier's 1,000/day cap is exhausted by full recomputes."** CONFIRMED as the cheap background traffic (220 tok/req) and ruled out as the leak, per §2B.

3. **"Mentor Chat calls weren't completing — the Advisor may be running on a truncated fragment."** DISPROVEN, and this was an agent error worth recording. The reasoning was: billing showed a ~65,000-token per-request ceiling; if Mentor Chat were succeeding at ~2.4M tokens, 2.4M-token requests would appear in that data; they don't; therefore the calls must be failing. **The 65,000 figure was an hourly *average* tokens-per-request, diluted by ~44 background calls/hour at 220 tokens each — not a per-request maximum.** It never excluded large calls, so the inference had no foundation. Settled by `grep "xAI Response Status Code:" app.log | sort | uniq -c`: **all 200s**, plus four 403s on Aug 17 21:08–21:09, and **zero 400s**. The calls were succeeding and being billed.

4. **"The 5-retry loop is amplifying cost — a 9.5MB upload that times out is re-uploaded up to five times per message."** DISPROVEN. `query_xai_api` does carry `max_retries = 5` at `timeout=150.0` (`ava_advisor.py:227–238`), so the amplifier is structurally real, but `grep -ci "timed out\|Max retries" app.log` returns **0**. It never fired. Cost was one clean expensive call per click, not several.

5. **"Guided Learning writes `strategies.json`; check whether its xAI calls load it whole."** Checked and cleared — `extract_strategies` / `extract_conceptual_ideas` (`wsgi_handler.py:87`, `:146`) send the submitted transcript only, and correctly place it *after* their static instructions.

---

## 4. Root Cause (confirmed)

**`load_strategies()` and `load_intelligence()` in `keepa_deals/ava_advisor.py` injected the entire knowledge base into every Advisor prompt.**

The "Tiered Strategy Injection" cap added in May 2026 (see §7.10) was applied only to Prime Picks Pass 2 and **never propagated to the Advisor**, even though both consume the same file.

- `ava_advisor.py:150` — `relevant_categories = set(["General", "Buying", "Risk"])`
- `ava_advisor.py:162` — `if not deal_context or (cat in relevant_categories) or (cat == "General")`

There was no cap and no confidence filter. With `deal_context` (Ava advice) it emitted **every** strategy in General/Buying/Risk. With no argument — the Mentor Chat path at `wsgi_handler.py:2866` — the `not deal_context` branch is true, so it emitted **the entire file, every category**, and `load_intelligence()` at `:2875` emitted all of `intelligence.json` alongside it.

Live file sizes: **`strategies.json` 8,439,801 bytes / 14,222 entries; `intelligence.json` 1,072,861 bytes.** One Mentor Chat message therefore carried **~9.5MB / ~2.4M prompt tokens**.

Billing cross-referenced against `ava_advisor` log lines proved the per-call cost directly:

| Date | Advisor calls | Excess tokens | Per call |
|---|---|---|---|
| Aug 22 | 1 | 511,904 | 511,904 |
| Aug 24 | 1 | 491,977 | 491,977 |
| Aug 23 | 2 | 938,258 | 469,129 |
| Aug 26 | 2 | 935,038 | 467,519 |
| Aug 29 | 8 | 3,473,136 | 434,142 |
| Aug 31 | 16 | 7,555,430 | 472,214 |

**434K–512K tokens per call across six independent days, scaling cleanly 1 → 2 → 8 → 16.** The "~480,000-token repeating unit recurring near-identically" described in the brief is **one Advisor click**. The Aug 31 10:00 UTC spike at 8× back-to-back was eight clicks, not eight chunks of a batch job.

The admin `/strategies` and `/intelligence` pages (`wsgi_handler.py:293`, `:330`) read the JSON files directly and were never part of this path.

---

## 5. Fix Implemented (PR #325, commit `789ceed`)

One file of logic. Three module-level constants in `keepa_deals/ava_advisor.py`, mirroring the bound `get_tiered_strategies()` already enforced:

```python
STRATEGY_CORE_CATEGORIES    = ("General", "Risk", "Buying", "Pricing")
MAX_STRATEGIES_PER_CATEGORY = 30      # 'High' confidence only
MAX_INTELLIGENCE_ITEMS      = 150
```

- **`load_strategies()`** now buckets by a **fixed** category allowlist (so a new category appearing in the file cannot grow the prompt), keeps only `confidence == 'High'`, and caps each bucket at 30. Seasonality is still added dynamically on textbook context. Ceiling: 120 strategies, or 150 with Seasonality.
- **`load_intelligence()`** takes a leading slice of 150. `intelligence.json` has no category dimension to tier on, so a flat cap is the analogue; 150 gives parity with the strategies ceiling.

Verified pre-merge against a synthetic corpus built to the exact production byte counts (8,463,506 bytes / 11,540 strategies; 1,245,500 bytes / 5,300 ideas):

| | Before | After |
|---|---|---|
| `load_strategies()` (Mentor Chat) | whole file, every category | 30,119 chars / ~7,529 tok / **120 lines** |
| `load_strategies(deal_context)` (Ava) | whole file, 3 categories | 37,799 chars / ~9,449 tok / **150 lines** |
| `load_intelligence()` | whole file | 28,949 chars / ~7,237 tok / **150 lines** |
| **Mentor Chat prompt** | **~2.4M tok** | **~16,000 tok** |
| **Ava advice prompt** | unbounded | **~22,900 tok** |

Output size is now **independent of file size** — adding strategies via Guided Learning no longer grows the prompt once a category is at cap. (Consistency check: the 120-line core selection lands at 30,119 chars, matching the ~29,703 chars documented for Pass 2's tiered injection.)

**Behaviour deltas beyond the cap**, both inherent to matching Pass 2, flagged before merge:
- Ava advice now also draws from the **Pricing** category (bounded, 30 max). Its previous allowlist was General/Buying/Risk only.
- Legacy plain-string strategies (no `category`/`confidence`) are skipped, as `get_tiered_strategies()` already does. Tim confirmed `strategies.json` holds **14,222 entries and 0 legacy plain strings**, so this drops nothing in practice.

Ava advice remains ~22,900 tokens because `platform_knowledge` — the 4-document set at **48,221 chars / 12,055 tokens** (`platform_knowledge.py`) — is a separate, still-uncapped input, deliberately left out of scope.

**Tests:** full suite passes. `test_smart_ingestor_batching` fails, but was confirmed to fail identically on clean HEAD via `git stash` — it asserts a 50-ASIN peek batch that the Aug 18 livelock fix deliberately changed to 15. Pre-existing, matches the open item in the Aug 18b log.

---

## 6. Deployment & Verification

PR #325 merged to `main` (`789ceed` → merge `203f83c`), pulled to the VPS, `deploy_update.sh` run.

**Measured hourly spend, Sep 7 (EST):**

| Hour | Advisor calls | Code | Cost |
|---|---|---|---|
| 17:00 | 1 | old | **$1.27** |
| 18:00 | 13 | old | **$11.08** |
| 19:00 → | live testing | **new** | **$0.01**, then **<$0.01/hr for 13 hours** |

**7-day spend down 36.6%**, still converging as the old-code days roll out of the window.

**Advice quality improved, not merely cheapened.** Live verification on the deployed build: Ava now correctly **passes** on a 4-drops/year book and **buys** a 119-drops/year book. The uncapped context had been diluting the signal, not enriching it — 14,222 rules of every confidence level crowded out the deal's own metrics. This is the outcome that matters most: the cheaper prompt is also the better one.

---

## 7. Open Items / Follow-Ups

- **The observed drop exceeds the projection and is unexplained — OPEN.** The pre-merge projection was ~480K → ~22,900 tokens, i.e. ~21×. Observed cost fell from $1.27 for a single call to effectively $0.00/hr. Candidate explanations, **none verified**, listed only to steer whoever picks this up: (a) a long-context surcharge tier in xAI's pricing, which would make cost fall super-linearly with prompt size; (b) hidden reasoning tokens on `grok-4-fast-reasoning` scaling with prompt size and billing as completion — these would not appear in the ~4-token *visible* completion average; (c) simply fewer Advisor clicks in the 13-hour post-deploy window than in the 18:00 test hour. Distinguishing them needs per-request billing detail, not code reading. Note also the pre-fix per-call spread ($1.27 for one call at 17:00 vs $0.852 average across 13 calls at 18:00) is itself consistent with a cache-hit-rate effect.
- **`platform_knowledge` is still uncapped** — 12,055 tokens on every Ava advice and every tooltip cache miss, and it dominates what remains of the Ava prompt.
- **Cache-prefix reorder (the "Fix A" proposal) was NOT done.** No xAI call site in the codebase currently holds a usable cache prefix. Worst offender is `generate_ava_advice` (`ava_advisor.py:435–487`): the system message is an f-string carrying the persona name, so position 0 of the prompt is variable and shards the cache four ways; the 12,055-token static doc set at `:438` and the 1,011-token `STRATEGIC_CORRECTIONS` at `:467` both sit *behind* per-deal variable content. Cacheable prefix today is ~15 tokens. `mentor_chat` (`wsgi_handler.py:2884–2906`) has the same single variable line ahead of an otherwise correctly-ordered prompt. `prime_picks_task` is already well ordered except for ~1,025 tokens of static instructions trailing the variable candidate block. This explains the $0.82–$2.60/M blended-rate spread and remains available as a follow-up — though at post-cap prompt sizes the payoff is far smaller than it would have been.
- **The XAI daily 1,000-call cap is not actually enforced.** `XaiTokenManager` is instantiated at module level in three separate modules, each holding its own in-memory `calls_today` and racing on `xai_token_state.json` (read at init, written after each call), across N Celery worker processes. Observed ~1,155 requests/day against a nominal 1,000 cap is consistent with the counter leaking.
- **The reasonableness cache can almost never hit.** `stable_calculations.py:38` builds its key from `price_usd`, `rank_info` (current sales rank), `trend_info` and `avg_3yr_usd` — all of which move on every refresh of the same ASIN, so every re-process is a fresh key and a fresh paid call. Fixing the key is a pure cost change that touches no prompt. `xai_cache.json` currently stands at 5,316,449 bytes and is rewritten in full on every `set()`.
- **Doc drift, unrelated to this change (flagged, not fixed):** `Feature_Guided_Learning_Strategies_Intelligence.md` §4 describes Semantic Homogenization as "Scheduled (Weekly)". `celery_config.py:30–40` contains only `smart-ingestor-run` and `janitor-clean-stale-deals` — homogenization is manual-trigger only. Whether the schedule was intended and never wired, or the doc is simply wrong, is an owner decision.
- **`test_smart_ingestor_batching`** still fails on clean HEAD (pre-existing, unrelated) — carried forward from the Aug 18b log.

---

## 8. Files Modified

- `keepa_deals/ava_advisor.py`: added `STRATEGY_CORE_CATEGORIES` / `MAX_STRATEGIES_PER_CATEGORY` / `MAX_INTELLIGENCE_ITEMS`; bounded `load_strategies()` and `load_intelligence()`.
- `AGENTS.md`: §1 locked xAI model corrected `grok-4-1-fast-reasoning` → `grok-4-fast-reasoning`, with a note that `grok-4.3` is the billing label.
- `Documentation/System_Architecture.md`: new "Advisor Context Caps (September 2026)" section; Mentor Chat no longer described as injecting the "full" knowledge base; strategy cap noted under "Advice from Ava".
- `Documentation/Token_Management_Strategy.md`: §2 Cost Control Mechanism now lists the Advisor context caps.
- `Documentation/Feature_Guided_Learning_Strategies_Intelligence.md`: §2 and §3 note that the pages show the full repository while the AI sees a bounded slice.
