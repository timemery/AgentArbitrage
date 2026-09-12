#!/bin/bash
# Run the whole test suite in ONE process, and fail the build if anything fails.
#
# WHY ONE PROCESS
# ---------------
# This script used to loop over tests/test_*.py and run each module in its own
# `python3 -m unittest` process, exiting 1 on the first failure. It did exit non-zero,
# but it could not gate the thing that actually mattered: with one module per process,
# cross-module interference is structurally invisible. In September 2026 that hid a
# defect where tests/test_approve_dedup.py installed MagicMocks into sys.modules at
# import time and never restored them, failing 25 tests in-suite - including
# tests/test_lightweight_upsert_preservation.py, the guard AGENTS.md 7.12 requires to
# stay green - while this script reported everything green.
#
# Running the suite in one process reproduces the real conditions, loads
# tests/conftest.py (which fails loudly if any module leaves sys.modules mutated), and
# reports every failure instead of stopping at the first one.
set -uo pipefail

cd "$(dirname "$0")" || exit 1

if ! python3 -c "import pytest" >/dev/null 2>&1; then
    echo "ERROR: pytest is not installed, so the test suite cannot be run or gated on."
    echo "Install the test dependencies first:"
    echo ""
    echo "    pip install -r requirements-dev.txt"
    echo ""
    exit 1
fi

echo "Running Core Tests (full suite, single process)..."
echo "----------------------------------------------------------------------"

# Scope and exclusions come from pytest.ini. Extra arguments are passed straight
# through, so `./run_tests.sh -k lightweight` and `./run_tests.sh -x` both work.
python3 -m pytest "$@"
status=$?

echo "----------------------------------------------------------------------"
if [ $status -ne 0 ]; then
    echo "TEST SUITE FAILED (exit $status)."
    exit $status
fi

echo "All Core Tests Passed."
