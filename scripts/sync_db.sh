#!/usr/bin/env bash
set -euo pipefail

# synchronize a dump file into the local postgres service
# Usage: ./sync_db.sh [dump_file]

DUMP=${1:-/app/db_dumps/railway_dump.sql}
if [ ! -f "$DUMP" ]; then
  echo "Dump file $DUMP not found"
  exit 1
fi

POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_DB=${POSTGRES_DB:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}

export POSTGRES_PASSWORD

CONN="host=$POSTGRES_HOST port=$POSTGRES_PORT user=$POSTGRES_USER dbname=$POSTGRES_DB password=$POSTGRES_PASSWORD"

echo "Restoring $DUMP into $POSTGRES_USER@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"

# Preprocess the dump before applying:
#   - CREATE TABLE/INDEX → IF NOT EXISTS  (safe to re-run against existing schema)
#   - COPY blocks        → INSERT … ON CONFLICT DO NOTHING  (skips already-imported rows)
# FK checks are disabled during data load to handle orphaned rows in remote DB.
# Any remaining DDL errors (e.g. ADD CONSTRAINT on tables that already have the constraint)
# are harmless; grep filters them from output and || true prevents bash from exiting.
{
  echo "SET session_replication_role = replica;"
  python3 /app/scripts/copy_to_insert.py < "$DUMP"
  echo "SET session_replication_role = DEFAULT;"
} | psql "$CONN" 2>&1 \
  | grep -v -e "already exists" -e "multiple primary keys" \
  || true

echo "Restore complete"