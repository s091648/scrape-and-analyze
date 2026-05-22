#!/usr/bin/env bash
set -euo pipefail

echo "=== Codespaces Init: Running database migrations ==="
cd /app
alembic upgrade head

echo "=== Codespaces Init: Creating admin user ==="
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}" \
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}" \
ADMIN_EMAIL=admin@example.com \
python scripts/create_admin.py

echo "=== Codespaces Init: Seeding fake data ==="
python scripts/seed_db.py

echo "=== Codespaces Init: Done ==="
