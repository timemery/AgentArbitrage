"""Suite-wide guard: no test module may leave `sys.modules` mutated behind it.

WHY THIS EXISTS
---------------
`tests/test_approve_dedup.py` used to assign `MagicMock()` into `sys.modules` for
'flask', 'celery_app', 'keepa_deals.db_utils', 'keepa_deals.janitor' and
'keepa_deals.ava_advisor' at import time, and never restore them. pytest imports every
test module before running any test, so those mocks were live for the whole session:
any module importing one of those names afterwards got a mock, and assertions compared
real values against mock attributes.

That single defect caused 25 of the 26 pre-existing full-suite failures, including
`tests/test_lightweight_upsert_preservation.py` — the guard `AGENTS.md` 7.12 says must
stay green, which passed 12/12 alone and failed in-suite. It was invisible because
`run_tests.sh` runs each module in its own process, where cross-module pollution cannot
occur.

THE INVARIANT
-------------
Every test module produces the same result run alone as it does in-suite. A module that
mutates `sys.modules` and does not restore it breaks that invariant for every module
collected after it, so this file fails the run rather than letting it happen quietly.

WHAT IS AND IS NOT A VIOLATION
------------------------------
Importing new modules is normal and is never flagged — only *deltas against what the
module found* are reported:

*   A `Mock` / `MagicMock` installed under any name.        -> violation
*   A pre-existing entry rebound to a different object.     -> violation
*   A pre-existing entry deleted.                           -> violation
*   A brand-new, real module appearing (an ordinary import) -> fine.

Mocking `sys.modules` inside a test is still fine, as long as it is scoped and restored
(`unittest.mock.patch.dict(sys.modules, ...)` does this). Where a private, unregistered
copy of a project module is wanted instead, use `tests/_real_module.load()`.
"""

import sys
from unittest.mock import Mock, NonCallableMock

import pytest

_MOCK_TYPES = (Mock, NonCallableMock)
_MISSING = object()

# nodeid -> dict(sys.modules) taken immediately before that module was imported.
_pre_import_snapshots = {}

# [(nodeid, [description, ...]), ...] recorded during collection, raised once collection
# finishes so the message can name every offender in one go.
_import_time_violations = []


def _describe_violations(snapshot):
    """Return a list of human-readable `sys.modules` changes relative to `snapshot`.

    Only differences are reported. Modules imported for the first time are expected and
    are not differences worth reporting, so they are skipped.
    """
    problems = []

    for name, module in sorted(sys.modules.items()):
        if not isinstance(module, _MOCK_TYPES):
            continue
        if snapshot.get(name, _MISSING) is module:
            continue  # already a mock before this module ran; not this module's doing
        problems.append(
            "sys.modules[{!r}] is a {} - a mock was installed and never removed".format(
                name, type(module).__name__))

    for name, original in sorted(snapshot.items()):
        current = sys.modules.get(name, _MISSING)
        if current is original:
            continue
        if current is _MISSING:
            problems.append(
                "sys.modules[{!r}] was deleted".format(name))
        elif not isinstance(current, _MOCK_TYPES):
            problems.append(
                "sys.modules[{!r}] was replaced with a different object "
                "({!r})".format(name, current))

    return problems


def _format(nodeid, problems):
    return (
        "\n{} mutated sys.modules and did not restore it.\n".format(nodeid)
        + "\n".join("  - " + p for p in problems)
        + "\n\nEvery test module must produce the same result run alone as it does "
          "in-suite.\nA leaked sys.modules entry is visible to every module collected "
          "after this one,\nso the suite stops here rather than reporting failures "
          "that belong to this module.\n\nScope the mocking (unittest.mock.patch.dict("
          "sys.modules, ...) restores on exit), or\nuse tests/_real_module.load() for a "
          "private, unregistered copy of a project module.\n"
    )


def pytest_collectstart(collector):
    """Snapshot sys.modules just before pytest imports a test module."""
    if isinstance(collector, pytest.Module):
        _pre_import_snapshots[collector.nodeid] = dict(sys.modules)


def pytest_collectreport(report):
    """Compare sys.modules against the snapshot right after the module was imported."""
    snapshot = _pre_import_snapshots.pop(report.nodeid, None)
    if snapshot is None:
        return
    problems = _describe_violations(snapshot)
    if problems:
        _import_time_violations.append(_format(report.nodeid, problems))


def pytest_collection_modifyitems(session, config, items):
    """Abort before any test runs if a module polluted sys.modules at import time.

    Import-time pollution is the dangerous case: pytest imports every test module before
    running the first test, so by the time tests execute the damage is already done and
    the resulting failures are attributed to innocent modules. Failing the run here keeps
    the blame where it belongs.
    """
    if _import_time_violations:
        raise pytest.UsageError(
            "sys.modules was polluted at import time:\n"
            + "\n".join(_import_time_violations))


@pytest.fixture(scope="module", autouse=True)
def _sys_modules_is_restored(request):
    """Catch a module that mutates sys.modules while its tests run."""
    snapshot = dict(sys.modules)
    yield
    problems = _describe_violations(snapshot)
    if problems:
        pytest.fail(_format(request.node.nodeid, problems), pytrace=False)
