#!/bin/bash
DB_FILE=${DATABASE_URL:-deals.db}
BACKUP_DIR="db_backups"

LATEST_BACKUP=$(ls -1 "$BACKUP_DIR" | grep "${DB_FILE##*/}" | tail -n 1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "No backups found for $DB_FILE"
    exit 1
fi

cp "$BACKUP_DIR/$LATEST_BACKUP" "$DB_FILE"

echo "Database restored from $BACKUP_DIR/$LATEST_BACKUP"
