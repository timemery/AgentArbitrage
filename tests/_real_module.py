"""Load a project module from disk, bypassing `sys.modules`.

WHY THIS EXISTS
---------------
`tests/test_approve_dedup.py` does this at import time and never restores it:

    sys.modules['flask'] = mock_flask
    sys.modules['celery_app'] = MagicMock()
    sys.modules['keepa_deals.db_utils'] = MagicMock()
    sys.modules['keepa_deals.janitor'] = MagicMock()
    sys.modules['keepa_deals.ava_advisor'] = MagicMock()

pytest imports every test module before running any test, so in a full-suite run
those MagicMocks are installed for the whole session. Any later module that does a
plain `import keepa_deals.db_utils` gets the mock, and assertions against it compare
real values to mock attributes.

This is a PRE-EXISTING suite defect. It is why `test_lightweight_upsert_preservation`
(the AGENTS.md 7.12 guard), `test_janitor`, `test_dashboard_filtering` and others
currently pass when run alone and fail in a full-suite run. It was reported to the
owner rather than fixed in the PR that added this file (AGENTS.md 3).

Tests that need the real module use `load('keepa_deals.db_utils')` and get a private
instance. It is deliberately NOT registered in `sys.modules`, so this changes nothing
for any other test module, in either direction.
"""

import importlib.util
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def load(dotted_name):
    """Return a fresh, private instance of the module named by `dotted_name`.

    Only handles modules with no relative imports, which covers the ones the
    pollution affects.
    """
    path = os.path.join(REPO_ROOT, *dotted_name.split('.')) + '.py'
    if not os.path.exists(path):
        raise ImportError("No module file at {}".format(path))
    spec = importlib.util.spec_from_file_location(
        '_real_' + dotted_name.replace('.', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
