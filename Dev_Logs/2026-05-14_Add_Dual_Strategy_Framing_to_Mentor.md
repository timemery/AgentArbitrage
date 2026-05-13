# 2026-05-14 Add Dual Strategy Framing to Mentor

## Overview
Added dual-strategy framing to the `STRATEGIC_CORRECTIONS` block in `keepa_deals/ava_advisor.py` to ensure that Mentor Advice and Mentor Chat appropriately weigh candidates against two distinct seller strategies: high-velocity flips and seasonal holds. Previously, the mentor showed a bias toward treating all candidates under a single high-velocity replens strategy, rejecting valid seasonal deals.

## Challenges
* Need to ensure both Mentor Advice and Mentor Chat receive the updated strategy logic.
* The strategy corrections block is maintained in `keepa_deals/ava_advisor.py` but used in both that file and `wsgi_handler.py`.

## Solutions
1. Appended the required dual-strategy framing language exactly as specified to the `STRATEGIC_CORRECTIONS` string in `keepa_deals/ava_advisor.py`.
2. Updated `wsgi_handler.py` to import `STRATEGIC_CORRECTIONS` from `keepa_deals.ava_advisor`.
3. Injected `{STRATEGIC_CORRECTIONS}` into the prompt template inside the `mentor_chat` endpoint in `wsgi_handler.py`.
4. Verified that all core tests pass with the changes applied.

## Status
Success. No issues encountered. Both AI mentor endpoints now correctly frame evaluations under the dual-strategy context.

## Deployment Notes
None beyond standard deployment. The changes are self-contained in Python logic and do not alter `.env` or Apache config. Tim can deploy normally via `./deploy_update.sh`.