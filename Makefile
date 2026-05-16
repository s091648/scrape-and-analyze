.PHONY: migrate migrate-remote migrate-down migrate-remote-down dump sync backfill backfill-dry-run create-admin scrape translate run retry-failed retry-failed-remote \
	test-src test-src-cov test-src-integration test-src-integration-cov \
	test-backend test-backend-cov test-backend-integration test-backend-integration-cov \
	test-frontend test-frontend-e2e test-all

# load environment file so targets can see variables like REMOTE_RAILWAY_DB_URL
ifneq (,$(wildcard .env))
include .env
export
endif

# default remote URL uses the variable from .env if present
REMOTE_URL ?= $(REMOTE_RAILWAY_DB_URL)
DUMP_FILE ?= /app/db_dumps/railway_dump.sql

# optional: override with LIMIT=50 to process only N articles
LIMIT ?=
_BACKFILL_ARGS := $(if $(LIMIT),--limit $(LIMIT),)

# Use ONLY when DB tables already exist but have no alembic_version record
# (e.g. migrating a legacy DB to alembic management). Do NOT use on a fresh DB.
pg_init:
	docker compose run --rm job_service alembic stamp baseline

migrate:
	@echo "Using REMOTE_URL=$(REMOTE_URL) and DUMP_FILE=$(DUMP_FILE)"
	docker compose run --rm job_service /app/scripts/db_migrate.sh

migrate-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	@echo "Running alembic upgrade head against Railway DB..."
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service /app/scripts/db_migrate.sh

# optional: override target revision with DOWNGRADE_REV=<revision> (default: -1, one step back)
DOWNGRADE_REV ?= -1

migrate-down:
	@echo "Running alembic downgrade $(DOWNGRADE_REV)..."
	docker compose run --rm job_service /app/scripts/db_migrate.sh downgrade $(DOWNGRADE_REV)

migrate-remote-down:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	@echo "Running alembic downgrade $(DOWNGRADE_REV) against Railway DB..."
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service /app/scripts/db_migrate.sh downgrade $(DOWNGRADE_REV)

# dump the remote database into the shared volume (default /app/db_dumps/railway_dump.sql)
dump:
	@echo "Using REMOTE_URL=$(REMOTE_URL) and DUMP_FILE=$(DUMP_FILE)"
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set"; exit 1)
	docker compose run --rm -e RAILWAY_DATABASE_URL="$(REMOTE_URL)" \
		job_service /app/scripts/dump_remote.sh "$(REMOTE_URL)" "$(DUMP_FILE)"

# restore last dump file into local postgres
sync:
	@echo "Using REMOTE_URL=$(REMOTE_URL) and DUMP_FILE=$(DUMP_FILE)"
	docker compose run --rm \
		-e PGPASSWORD=$${POSTGRES_PASSWORD:-postgres} \
		job_service /app/scripts/sync_db.sh "$(DUMP_FILE)"

create-admin:
	docker compose run --rm job_service python scripts/create_admin.py

backfill:
	docker compose run --rm job_service python /app/scripts/backfill_tags.py $(_BACKFILL_ARGS)

backfill-dry-run:
	docker compose run --rm job_service python /app/scripts/backfill_tags.py --dry-run $(_BACKFILL_ARGS)

# Scrape (and optionally analyze) from a specific source.
# Usage:
#   make scrape SOURCE=rss
#   make scrape SOURCE=arxiv LIMIT=10
#   make scrape SOURCE=arxiv DAYS_BACK=-1  # no date filter (all articles)
#   make scrape SOURCE=blog NO_ANALYZE=1
SOURCE ?= rss
NO_ANALYZE ?=
_DAYS_BACK := $(if $(DAYS_BACK),--days-back $(DAYS_BACK),)
_SCRAPE_ARGS := --source $(SOURCE) $(_DAYS_BACK) $(if $(LIMIT),--limit $(LIMIT),) $(if $(NO_ANALYZE),--no-analyze,)

scrape:
	docker compose run --rm job_service python /app/scripts/scrape.py $(_SCRAPE_ARGS)

# Translate article analyses to another language.
# Usage:
#   make translate LANG=zh-TW
#   make translate LANG=zh-TW LIMIT=50
LANG ?= zh-TW
translate:
	docker compose run --rm job_service python -m src.entrypoints.cli.translate --language $(LANG) $(if $(LIMIT),--limit $(LIMIT),)

run:
	docker compose run --rm app python -m src.entrypoints.cli.main

# optional: override with HOURS=48 LIMIT=20
_RETRY_ARGS := $(if $(LIMIT),--limit $(LIMIT),) $(if $(HOURS),--hours $(HOURS),)

retry-failed:
	docker compose run --rm job_service python /app/scripts/retry_failed.py $(_RETRY_ARGS)

retry-failed-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service python /app/scripts/retry_failed.py $(_RETRY_ARGS)

# ─── src/ tests ───────────────────────────────────────────────────────────────

test-src:
	docker compose run --rm test_service python -m pytest src/tests/unit/ -v --tb=short

test-src-cov:
	docker compose run --rm test_service python -m pytest \
		src/tests/unit/ \
		-v --tb=short \
		--cov=src \
		--cov-report=html:src/tests/htmlcov \
		--cov-report=term

test-src-integration:
	docker compose run --rm test_service python -m pytest src/tests/integration/ -v --tb=short -m integration

test-src-integration-cov:
	docker compose run --rm test_service python -m pytest \
		src/tests/integration/ \
		-v --tb=short -m integration \
		--cov=src \
		--cov-report=html:src/tests/htmlcov-integration \
		--cov-report=term

# ─── backend/ tests ───────────────────────────────────────────────────────────

test-backend:
	docker compose run --rm test_service python -m pytest backend/tests/ \
		--ignore=backend/tests/integration/ \
		-v --tb=short

test-backend-cov:
	docker compose run --rm test_service python -m pytest backend/tests/ \
		--ignore=backend/tests/integration/ \
		-v --tb=short \
		--cov=backend \
		--cov-report=html:backend/tests/htmlcov \
		--cov-report=term

test-backend-integration:
	docker compose run --rm test_service python -m pytest backend/tests/integration/ -v --tb=short -m integration

test-backend-integration-cov:
	docker compose run --rm test_service python -m pytest \
		backend/tests/integration/ \
		-v --tb=short -m integration \
		--cov=backend \
		--cov-report=html:backend/tests/htmlcov-integration \
		--cov-report=term

# ─── frontend/ tests ──────────────────────────────────────────────────────────

test-frontend:
	docker compose run --rm frontend npm run test

test-frontend-e2e:
	docker compose run --rm frontend npm run test:e2e

# ─── combined ─────────────────────────────────────────────────────────────────

# Run unit + integration tests for all three services; always runs to completion and prints a summary
test-all:
	bash scripts/run_tests.sh

