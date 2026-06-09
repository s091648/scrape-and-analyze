.PHONY: migrate migrate-remote migrate-down migrate-remote-down dump sync sync-to-remote \
	backfill backfill-dry-run backfill-embeddings backfill-embeddings-dry-run \
	backfill-tag-group-embeddings backfill-tag-group-embeddings-dry-run \
	backfill-embeddings-remote backfill-tag-group-embeddings-remote \
	backfill-tag-group-definitions backfill-tag-group-definitions-dry-run \
	backfill-tag-group-definitions-remote \
	audit-tag-groups \
	backfill-suggestions backfill-suggestions-dry-run \
	data-migrate data-migrate-list data-migrate-down \
	create-admin scrape translate run retry-failed retry-failed-remote \
	test-src test-src-cov test-src-integration test-src-integration-cov \
	test-backend test-backend-cov test-backend-integration test-backend-integration-cov \
	test-frontend test-frontend-cov test-frontend-e2e test-all \
	storybook build-storybook \
	site-preview uml uml-frontend-deps uml-frontend-context

# load environment file so targets can see variables like REMOTE_RAILWAY_DB_URL
ifneq (,$(wildcard .env))
include .env
export
endif

# ENV selects the target remote database (default: staging)
# Usage: make migrate-remote              → staging
#        make migrate-remote ENV=production → production
ENV ?= staging
REMOTE_URL ?= $(if $(filter production,$(ENV)),$(REMOTE_RAILWAY_DB_URL),$(REMOTE_RAILWAY_STAGING_DB_URL))
DUMP_FILE ?= /app/db_dumps/railway_dump.sql

# optional: override with LIMIT=50 to process only N articles
LIMIT ?=
_BACKFILL_ARGS := $(if $(LIMIT),--limit $(LIMIT),)

# optional: override upgrade target with UPGRADE_REV=<revision> (default: head)
UPGRADE_REV ?=

migrate:
	@echo "Using REMOTE_URL=$(REMOTE_URL)"
	docker compose run --rm job_service /app/scripts/db_migrate.sh upgrade $(UPGRADE_REV)

migrate-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set — check REMOTE_RAILWAY_STAGING_DB_URL (or REMOTE_RAILWAY_DB_URL for ENV=production) in .env"; exit 1)
	@echo "Running alembic upgrade $(or $(UPGRADE_REV),head) against Railway $(ENV) DB..."
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service /app/scripts/db_migrate.sh upgrade $(UPGRADE_REV)

# optional: override target revision with DOWNGRADE_REV=<revision> (default: -1, one step back)
DOWNGRADE_REV ?= -1

migrate-down:
	@echo "Running alembic downgrade $(DOWNGRADE_REV)..."
	docker compose run --rm job_service /app/scripts/db_migrate.sh downgrade $(DOWNGRADE_REV)

migrate-remote-down:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set — check REMOTE_RAILWAY_STAGING_DB_URL (or REMOTE_RAILWAY_DB_URL for ENV=production) in .env"; exit 1)
	@echo "Running alembic downgrade $(DOWNGRADE_REV) against Railway $(ENV) DB..."
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

# restore last dump file into a remote (Railway) database
# Usage:
#   make sync-to-remote              → restore into staging (default)
#   make sync-to-remote ENV=production → restore into production (dangerous!)
sync-to-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set — check REMOTE_RAILWAY_STAGING_DB_URL in .env"; exit 1)
	@echo "Restoring $(DUMP_FILE) into Railway $(ENV) DB..."
	docker compose run --rm job_service /app/scripts/sync_remote.sh "$(REMOTE_URL)" "$(DUMP_FILE)"

create-admin:
	docker compose run --rm job_service python scripts/create_admin.py

backfill:
	docker compose run --rm job_service python /app/scripts/backfill_tags.py $(_BACKFILL_ARGS)

backfill-dry-run:
	docker compose run --rm job_service python /app/scripts/backfill_tags.py --dry-run $(_BACKFILL_ARGS)

backfill-embeddings:
	docker compose run --rm job_service python /app/scripts/backfill_tag_embeddings.py $(_BACKFILL_ARGS)

backfill-embeddings-dry-run:
	docker compose run --rm job_service python /app/scripts/backfill_tag_embeddings.py --dry-run $(_BACKFILL_ARGS)

backfill-tag-group-embeddings:
	docker compose run --rm job_service python /app/scripts/backfill_tag_embeddings.py --only tag-groups $(_BACKFILL_ARGS)

backfill-tag-group-embeddings-dry-run:
	docker compose run --rm job_service python /app/scripts/backfill_tag_embeddings.py --only tag-groups --dry-run $(_BACKFILL_ARGS)

backfill-embeddings-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	docker compose run --rm job_service python /app/scripts/backfill_tag_embeddings.py --remote $(_BACKFILL_ARGS)

backfill-tag-group-embeddings-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	docker compose run --rm job_service python /app/scripts/backfill_tag_embeddings.py --only tag-groups --remote $(_BACKFILL_ARGS)

NAME ?=

data-migrate:
	docker compose run --rm job_service python /app/scripts/run_data_migrations.py

data-migrate-list:
	docker compose run --rm job_service python /app/scripts/run_data_migrations.py --list

data-migrate-down:
	@test -n "$(NAME)" || (echo "NAME must be set (e.g. NAME=001_backfill_tag_group_definitions)"; exit 1)
	docker compose run --rm job_service python /app/scripts/run_data_migrations.py --down $(NAME)

backfill-suggestions:
	docker compose run --rm job_service python /app/scripts/backfill_tag_suggestions.py

backfill-suggestions-dry-run:
	docker compose run --rm job_service python /app/scripts/backfill_tag_suggestions.py --dry-run

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

test-frontend-cov:
	docker compose run --rm frontend npm run test:coverage

test-frontend-e2e:
	docker compose run --rm frontend npm run test:e2e

# ─── storybook ────────────────────────────────────────────────────────────────

storybook:
	docker compose run --rm -p 6006:6006 frontend npm run storybook

build-storybook:
	docker compose run --rm -p 6006:6006 frontend sh -c "npm run build-storybook && npx serve -s storybook-static -l 6006"

# ─── site preview ─────────────────────────────────────────────────────────────

site-preview:
	node -e "const{rmSync,cpSync}=require('fs');rmSync('site/specs',{recursive:true,force:true});cpSync('specs','site/specs',{recursive:true})"
	cd site && npm install && npm run dev

# ─── combined ─────────────────────────────────────────────────────────────────

# Run unit + integration tests for all three services; always runs to completion and prints a summary
test-all:
	bash scripts/run_tests.sh

# ─── UML generation ──────────────────────────────────────────────────────────

uml: uml-backend uml-frontend

uml-backend:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" job_service sh -c "python /app/scripts/generate_uml.py"

uml-frontend: uml-frontend-deps uml-frontend-context

uml-frontend-deps:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" frontend sh -c "npx --yes madge --json --extensions ts,tsx --ts-config tsconfig.json app/ lib/ components/ > /app/site/guide/architecture/frontend-deps.json"

uml-frontend-context:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" frontend sh -c "node /app/scripts/generate-frontend-context.mjs"

