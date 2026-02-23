#!/usr/bin/env bash
set -euo pipefail

# run inside container
cd /app

echo "Running alembic upgrade head (DATABASE_URL=${DATABASE_URL:-<unset>})"
alembic upgrade head
