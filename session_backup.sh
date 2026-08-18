#!/bin/bash
# session_backup.sh
#
# End-of-session safety net. Two independent backups, in order:
#   1. Snapshots deals.db via the existing ./backup_db.sh (timestamped, into db_backups/).
#   2. Commits any current changes and PUSHES them to a dated branch: backup/YYYY-MM-DD
#
# PUSH-ONLY GUARANTEE — do not add operations that violate this:
#   This script NEVER runs pull, fetch, merge, rebase, checkout, switch, reset,
#   clean, stash, or push --force. It cannot overwrite, discard, or revert any
#   local file, and it never moves HEAD or touches the working tree.
#   The commit is made on whatever branch you are already on; the push uses an
#   explicit refspec (HEAD:refs/heads/backup/DATE) so the backup branch is created
#   and updated on the remote WITHOUT any local branch switch.
#
# Note: db_backups/, deals.db*, and .env are all gitignored, so the database
# snapshot and your credentials are never committed or pushed by step 2/3.
#
# Usage:  ./session_backup.sh
#
# Exit code: 0 if every step succeeded, 1 if any step failed or was skipped.

# Deliberately NOT using `set -e`: a failure in one step (e.g. a missing
# database file) must not prevent the git backup in the later steps from running.

# Always operate from the repo root, regardless of the caller's working directory.
cd "$(dirname "$0")" || { echo "FATAL: cannot cd to script directory."; exit 1; }

DATE=$(date +"%Y-%m-%d")
STAMP=$(date +"%Y-%m-%d %H:%M:%S")
START_EPOCH=$(date +%s)
BACKUP_BRANCH="backup/$DATE"
DB_FILE=${DATABASE_URL:-deals.db}
BACKUP_DIR="db_backups"
FAILED=0

echo "=================================================="
echo " Agent Arbitrage — Session Backup"
echo " Time:          $STAMP"
echo " Repo root:     $(pwd)"
echo " Backup branch: $BACKUP_BRANCH"
echo "=================================================="
echo ""

# --- Sanity: must be inside a git work tree with at least one commit ---
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "FATAL: $(pwd) is not a git repository. Aborting."
    exit 1
fi
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
    echo "FATAL: repository has no commits yet (unborn HEAD). Nothing to push."
    exit 1
fi

# =========================================================
# Step 1/3 — Database snapshot via existing backup_db.sh
# =========================================================
echo "--- Step 1/3: Database snapshot (./backup_db.sh) ---"

if [ ! -f "./backup_db.sh" ]; then
    echo "SKIPPED: ./backup_db.sh not found."
    FAILED=1
elif [ ! -f "$DB_FILE" ]; then
    echo "SKIPPED: database file '$DB_FILE' does not exist in $(pwd)."
    echo "         (Set DATABASE_URL if your database lives elsewhere.)"
    echo "         Nothing to snapshot — continuing to the git backup."
    FAILED=1
else
    echo "Database file: $DB_FILE ($(du -h "$DB_FILE" | cut -f1))"
    bash ./backup_db.sh
    BACKUP_RC=$?

    # backup_db.sh ends in an `echo`, so it always exits 0 even if the copy
    # failed. Verify independently that a fresh snapshot actually landed on disk.
    NEW_BAK=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "*.bak" \
                   -newermt "@$((START_EPOCH - 1))" 2>/dev/null | sort | tail -n 1)

    if [ $BACKUP_RC -ne 0 ]; then
        echo "FAILED: backup_db.sh exited with status $BACKUP_RC."
        FAILED=1
    elif [ -z "$NEW_BAK" ] || [ ! -s "$NEW_BAK" ]; then
        echo "FAILED: backup_db.sh reported success but no new non-empty"
        echo "        snapshot appeared in $BACKUP_DIR/. Check permissions/disk space."
        FAILED=1
    else
        echo "VERIFIED: snapshot written -> $NEW_BAK ($(du -h "$NEW_BAK" | cut -f1))"
    fi
fi
echo ""

# =========================================================
# Step 2/3 — Stage and commit current changes
# =========================================================
echo "--- Step 2/3: Commit current changes ---"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
echo "Committing on: $CURRENT_BRANCH  (HEAD $(git rev-parse --short HEAD))"
echo ""
echo "Working tree status before staging:"
git status --short
echo ""

git add -A
ADD_RC=$?
if [ $ADD_RC -ne 0 ]; then
    echo "FAILED: 'git add -A' exited with status $ADD_RC. Skipping commit."
    FAILED=1
elif git diff --cached --quiet; then
    echo "Nothing new to stage — working tree already clean."
    echo "Proceeding to push the existing HEAD to $BACKUP_BRANCH."
else
    echo "Staged changes:"
    git diff --cached --stat
    echo ""
    git commit -m "Session backup: $STAMP"
    COMMIT_RC=$?
    if [ $COMMIT_RC -ne 0 ]; then
        echo "FAILED: 'git commit' exited with status $COMMIT_RC."
        FAILED=1
    fi
fi
echo ""
echo "HEAD is now: $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
echo ""

# =========================================================
# Step 3/3 — Push HEAD to the dated backup branch (push-only)
# =========================================================
echo "--- Step 3/3: Push to origin/$BACKUP_BRANCH ---"
echo "Command: git push origin HEAD:refs/heads/$BACKUP_BRANCH"
echo ""

# No '-u': this push targets a rotating dated branch. Setting upstream would
# silently repoint '$CURRENT_BRANCH' at the backup branch and hijack your next
# plain 'git push'. No '--force' either: a rejected push means the remote holds
# work this HEAD does not contain, and destroying it is exactly what a backup
# script must never do.
PUSH_RC=1
DELAY=2
for ATTEMPT in 1 2 3; do
    if [ $ATTEMPT -gt 1 ]; then
        echo "Retrying in ${DELAY}s (attempt $ATTEMPT of 3)..."
        sleep $DELAY
        DELAY=$((DELAY * 2))
    fi
    git push origin "HEAD:refs/heads/$BACKUP_BRANCH"
    PUSH_RC=$?
    [ $PUSH_RC -eq 0 ] && break
    echo "Push attempt $ATTEMPT failed (status $PUSH_RC)."
done

if [ $PUSH_RC -eq 0 ]; then
    echo ""
    echo "PUSHED: $(git rev-parse --short HEAD) -> origin/$BACKUP_BRANCH"
else
    echo ""
    echo "FAILED: could not push to origin/$BACKUP_BRANCH after 3 attempts."
    echo "        If this was rejected as non-fast-forward, the remote branch"
    echo "        holds commits this HEAD does not. This script will NOT force-push."
    echo "        Inspect it manually before overwriting anything."
    FAILED=1
fi
echo ""

# =========================================================
# Summary
# =========================================================
echo "=================================================="
if [ $FAILED -eq 0 ]; then
    echo " SESSION BACKUP COMPLETE — all steps succeeded."
else
    echo " SESSION BACKUP FINISHED WITH WARNINGS."
    echo " One or more steps failed or were skipped; see output above."
fi
echo " Local files were never modified: no pull, fetch, merge,"
echo " checkout, reset, or force-push was performed."
echo "=================================================="

exit $FAILED
