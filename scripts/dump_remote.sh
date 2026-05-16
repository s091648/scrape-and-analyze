#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./dump_remote.sh <remote_db_url> [output_file]
# or rely on RAILWAY_DATABASE_URL env var

REMOTE=${1:-${RAILWAY_DATABASE_URL:-}}
if [ -z "$REMOTE" ]; then
  echo "Usage: $0 <remote_db_url> or set RAILWAY_DATABASE_URL env"
  exit 1
fi

OUT=${2:-/app/db_dumps/railway_dump.sql}

echo "Dumping remote database ($REMOTE) to $OUT"
# pg_dump should be installed in this image (postgresql-client package)
pg_dump "$REMOTE" -Fp -O -x --column-inserts --on-conflict-do-nothing -f "$OUT"

echo "Dump complete"