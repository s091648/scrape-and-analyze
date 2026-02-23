#!/usr/bin/env bash
set -euo pipefail

# synchronize a dump file into the local postgres service
# Usage: ./sync_db.sh [dump_file]

DUMP=${1:-/app/db_dumps/railway_dump.sql}
if [ ! -f "$DUMP" ]; then
  echo "Dump file $DUMP not found"
  exit 1
fi

PGHOST=${PGHOST:-postgres}
PGUSER=${PGUSER:-digital_twins}
PGDATABASE=${PGDATABASE:-digital_twins}
PGPASSWORD=${PGPASSWORD:-digital_twins}

export PGPASSWORD

echo "Restoring $DUMP into $PGUSER@$PGHOST/$PGDATABASE"
psql "host=$PGHOST user=$PGUSER dbname=$PGDATABASE" < "$DUMP"

echo "Restore complete"