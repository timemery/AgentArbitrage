#!/bin/bash
DB_FILE=${DATABASE_URL:-deals.db}
BACKUP_DIR="db_backups"
TIMESTAMP=$(date +"%Y%m%d%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_FILE##*/}.$TIMESTAMP.bak"

mkdir -p "$BACKUP_DIR"
cp "$DB_FILE" "$BACKUP_FILE"

echo "Database backed up to $BACKUP_FILE"
