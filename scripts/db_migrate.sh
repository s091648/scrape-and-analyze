#!/usr/bin/env bash
set -euo pipefail

# run inside container
cd /app

MODE="${1:-upgrade}"
REV="${2:-}"

if [ "$MODE" = "downgrade" ]; then
    TARGET="${REV:--1}"
    echo "Running alembic downgrade ${TARGET} (DATABASE_URL=${DATABASE_URL:-<unset>})"
    alembic downgrade "$TARGET"
else
    TARGET="${REV:-head}"
    echo "Running alembic upgrade ${TARGET} (DATABASE_URL=${DATABASE_URL:-<unset>})"
    alembic upgrade "$TARGET"
fi
