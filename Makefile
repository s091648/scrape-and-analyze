.PHONY: migrate migrate-remote dump sync backfill backfill-dry-run create-admin scrape run

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
#   make scrape SOURCE=blog NO_ANALYZE=1
SOURCE ?= rss
NO_ANALYZE ?=
_SCRAPE_ARGS := --source $(SOURCE) $(if $(LIMIT),--limit $(LIMIT),) $(if $(NO_ANALYZE),--no-analyze,)

scrape:
	docker compose run --rm job_service python /app/scripts/scrape.py $(_SCRAPE_ARGS)

run:
	docker compose run --rm app python -m src.main

# 基礎測試指令
test:
	docker compose run --rm app python -m pytest tests/unit/ -v --tb=short

# 產生覆蓋率報告的測試指令 (HTML 會出現在專案的 tests/htmlcov/ 目錄下)
test-cov:
	docker compose run --rm app python -m pytest \
		tests/unit/ \
		-v --tb=short \
		--cov=src \
		--cov-report=html:tests/htmlcov \
		--cov-report=term

# Integration tests (requires postgres — `docker compose up -d postgres` first if needed)
test-integration:
	docker compose run --rm app python -m pytest tests/integration/ -v --tb=short -m integration

# Integration tests with coverage report
test-integration-cov:
	docker compose run --rm app python -m pytest \
		tests/integration/ \
		-v --tb=short -m integration \
		--cov=src \
		--cov-report=html:tests/htmlcov-integration \
		--cov-report=term

# Run all tests (unit + integration) with combined coverage
test-all-cov:
	docker compose run --rm app python -m pytest \
		tests/ \
		-v --tb=short \
		--cov=src \
		--cov-report=html:tests/htmlcov-all \
		--cov-report=term