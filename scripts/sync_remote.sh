#!/usr/bin/env bash
set -euo pipefail

# Restore a dump file into a remote (Railway) PostgreSQL database.
# Mirrors the preprocessing in sync_db.sh (copy_to_insert conversion + FK bypass),
# but targets a remote URL instead of the local postgres service.
#
# Usage:
#   ./sync_remote.sh <remote_db_url> [dump_file]

REMOTE=${1:-}
DUMP=${2:-/app/db_dumps/railway_dump.sql}

if [ -z "$REMOTE" ]; then
  echo "Usage: $0 <remote_db_url> [dump_file]"
  exit 1
fi

if [ ! -f "$DUMP" ]; then
  echo "Dump file $DUMP not found — run 'make dump ENV=production' first"
  exit 1
fi

echo "Restoring $DUMP into remote DB..."
{
  echo "SET session_replication_role = replica;"
  python3 /app/scripts/copy_to_insert.py < "$DUMP"
  echo "SET session_replication_role = DEFAULT;"
} | psql "$REMOTE" 2>&1 \
  | grep -v -e "already exists" -e "multiple primary keys" \
  || true

echo "Restore complete"
