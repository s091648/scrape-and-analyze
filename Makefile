.PHONY: migrate migrate-remote migrate-down migrate-remote-down dump sync sync-to-remote \
	backfill backfill-dry-run backfill-embeddings backfill-embeddings-dry-run \
	backfill-tag-group-embeddings backfill-tag-group-embeddings-dry-run \
	backfill-embeddings-remote backfill-tag-group-embeddings-remote \
	backfill-tag-group-definitions backfill-tag-group-definitions-dry-run \
	backfill-tag-group-definitions-remote \
	audit-tag-groups \
	backfill-suggestions backfill-suggestions-dry-run \
	backfill-webp-covers backfill-webp-covers-dry-run backfill-webp-covers-remote \
	backfill-r2-cache-control backfill-r2-cache-control-dry-run backfill-r2-cache-control-remote \
	data-migrate data-migrate-list data-migrate-one data-migrate-down \
	create-admin scrape translate translate-remote run weekly-report weekly-report-remote retry-failed retry-failed-remote \
	backfill-rag backfill-rag-remote \
	rebuild-search-index rebuild-search-index-remote \
	test-src test-src-cov test-src-integration test-src-integration-cov \
	test-backend test-backend-cov test-backend-integration test-backend-integration-cov \
	test-frontend test-frontend-cov test-frontend-e2e test-all \
	storybook build-storybook \
	lighthouse-check \
	site-preview uml uml-backend uml-db-schema uml-exceptions uml-terraform-docs uml-terraform-modules uml-frontend uml-frontend-deps uml-frontend-context \
	terraform-fmt terraform-validate terraform-plan terraform-apply terraform-drift-check terraform-force-unlock push-tfvars pull-railway-variables push-railway-variables check-railway-variables \
	railway-cli railway-config-plan railway-config-apply railway-config-pull railway-config-migrate

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

# Run one specific pending data migration by name, skipping every other pending
# one — useful for testing a migration you're actively writing without also
# triggering unrelated ones. Usage: make data-migrate-one NAME=002_backfill_arxiv_id
data-migrate-one:
	@test -n "$(NAME)" || (echo "NAME must be set (e.g. NAME=002_backfill_arxiv_id)"; exit 1)
	docker compose run --rm job_service python /app/scripts/run_data_migrations.py --name $(NAME)

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

translate-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set — check REMOTE_RAILWAY_STAGING_DB_URL (or REMOTE_RAILWAY_DB_URL for ENV=production) in .env"; exit 1)
	@echo "Running translation ($(LANG)) against Railway $(ENV) DB..."
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service python -m src.entrypoints.cli.translate --language $(LANG) $(if $(LIMIT),--limit $(LIMIT),)

run:
	docker compose run --rm app python -m src.entrypoints.cli.main

# Generate weekly article summary report(s).
# Usage:
#   make weekly-report
#   make weekly-report TOPIC_ID=<uuid>
#   make weekly-report TOPIC_ID=<uuid> WEEK_START=2025-01-06
#   make weekly-report WEEK_START=2025-01-06 FORCE=1   # regenerate even if this week's report already exists
#   make weekly-report-remote                          # staging DB (default ENV)
#   make weekly-report-remote ENV=production            # production DB
TOPIC_ID ?=
WEEK_START ?=
FORCE ?=
_WEEKLY_ARGS := $(if $(TOPIC_ID),--topic-id $(TOPIC_ID),) $(if $(WEEK_START),--week-start $(WEEK_START),) $(if $(FORCE),--force,)

weekly-report:
	docker compose run --rm job_service python -m src.entrypoints.cli.weekly_report $(_WEEKLY_ARGS)

weekly-report-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set — check REMOTE_RAILWAY_STAGING_DB_URL (or REMOTE_RAILWAY_DB_URL for ENV=production) in .env"; exit 1)
	@echo "Running weekly report against Railway $(ENV) DB..."
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service python -m src.entrypoints.cli.weekly_report $(_WEEKLY_ARGS)

# optional: override with HOURS=48 LIMIT=20
_RETRY_ARGS := $(if $(LIMIT),--limit $(LIMIT),) $(if $(HOURS),--hours $(HOURS),)

retry-failed:
	docker compose run --rm job_service python /app/scripts/retry_failed.py $(_RETRY_ARGS)

retry-failed-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service python /app/scripts/retry_failed.py $(_RETRY_ARGS)

# Backfill RAG vector-store ingestion for previously-scraped articles (has_vectors=false).
# Usage:
#   make backfill-rag
#   make backfill-rag LIMIT=5
#   make backfill-rag CONCURRENCY=3
CONCURRENCY ?=
_BACKFILL_RAG_ARGS := $(if $(LIMIT),--limit $(LIMIT),) $(if $(CONCURRENCY),--concurrency $(CONCURRENCY),)

backfill-rag:
	docker compose run --rm job_service python -m src.entrypoints.cli.backfill_rag $(_BACKFILL_RAG_ARGS)

backfill-rag-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service python -m src.entrypoints.cli.backfill_rag $(_BACKFILL_RAG_ARGS)

# optional: override with MIN_DOC_FREQ=1
MIN_DOC_FREQ ?=
_REBUILD_SEARCH_INDEX_ARGS := $(if $(MIN_DOC_FREQ),--min-doc-freq $(MIN_DOC_FREQ),)

rebuild-search-index:
	docker compose run --rm job_service python /app/scripts/rebuild_search_index.py $(_REBUILD_SEARCH_INDEX_ARGS)

rebuild-search-index-remote:
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set (check REMOTE_RAILWAY_DB_URL in .env)"; exit 1)
	docker compose run --rm -e DATABASE_URL="$(REMOTE_URL)" job_service python /app/scripts/rebuild_search_index.py $(_REBUILD_SEARCH_INDEX_ARGS)

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

# `docker compose run` overrides the frontend service's Dockerfile CMD entirely, so the
# playwright-install-on-startup step there never runs here — install explicitly first
# (fast no-op when the cached browsers already match the installed playwright-core version).
test-frontend-e2e:
	docker compose run --rm frontend sh -c "npx playwright install && npm run test:e2e"

# ─── lighthouse performance check ──────────────────────────────────────────────

# Run a Lighthouse performance check across configured routes and produce a
# consolidated, Traditional-Chinese Markdown report (specs/022-lighthouse-performance-check).
# Defaults to the frontend_prod service — the production-build frontend — since dev-mode
# numbers are not representative of real LCP/Web Vitals (see docker-compose.yml comments).
# Usage:
#   make lighthouse-check
#   make lighthouse-check LIGHTHOUSE_URL=http://frontend_prod:3000
#   make lighthouse-check LIGHTHOUSE_ROUTES="/,/articles"
# Prerequisites: postgres, redis, backend, and frontend_prod must already be running
# (docker compose up -d postgres redis backend && docker compose --profile tools up -d --build frontend_prod).
# MSYS_NO_PATHCONV=1: on Windows + Git Bash, MSYS auto-converts a bare "/" argument into a
# Windows path (e.g. "C:/Program Files/Git/"), silently corrupting the root route. This env
# var disables that conversion; it's a no-op on Linux/Mac.
LIGHTHOUSE_URL ?= http://frontend_prod:3000
LIGHTHOUSE_ROUTES ?= /,/articles,/graph,/tags

lighthouse-check:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(CURDIR)/lighthouse-reports:/app/lighthouse-reports" frontend \
		node scripts/lighthouse-check.mjs --url "$(LIGHTHOUSE_URL)" --routes "$(LIGHTHOUSE_ROUTES)"

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

uml: uml-backend uml-db-schema uml-exceptions uml-terraform-docs uml-terraform-modules uml-frontend

uml-backend:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" job_service sh -c "python /app/scripts/generate_uml.py"

uml-db-schema:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" job_service sh -c "python /app/scripts/generate_db_schema.py"

uml-exceptions:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" job_service sh -c "python /app/scripts/generate_exceptions.py"

# Static HCL parsing only (python-hcl2) — never calls `terraform` itself, no
# credentials needed. See site/guide/architecture/terraform-services.md.
uml-terraform-docs:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" job_service sh -c "python /app/scripts/generate_terraform_docs.py"

# Per-module interface reference (inputs/outputs/requirements) via the official
# terraform-docs tool — complements uml-terraform-docs above, which documents
# *usage* (which service sets which variable), not each module's own interface.
# Runs the official image directly (not job_service — it's a Go binary, no
# reason to bundle it into the Python image); output is build-artifact-only
# fragments consumed by site/guide/architecture/terraform-modules.md via
# VitePress's @include, never hand-maintained or committed back into the
# modules' own directories.
TF_DOCS_IMAGE := quay.io/terraform-docs/terraform-docs:0.20.0
# Source tree (gitignored), not site/public/ — these are raw fragments with no
# frontmatter, spliced into site/guide/architecture/terraform-modules.md via
# VitePress's <!--@include:--> at build time; never meant to be visited as
# their own pages, unlike the site/public/*.json data files the Vue viewers fetch.
TF_DOCS_OUT := site/guide/architecture/terraform-modules

uml-terraform-modules:
	@mkdir -p $(TF_DOCS_OUT)
	@for m in github-ci-config; do \
		echo "terraform-docs: modules/$$m"; \
		MSYS_NO_PATHCONV=1 docker run --rm -v "$(CURDIR)/infra/terraform/railway:/terraform-docs:ro" -w /terraform-docs \
			$(TF_DOCS_IMAGE) --config /terraform-docs/.terraform-docs.yml markdown table modules/$$m \
			| python scripts/wrap_terraform_module_doc.py "$$m" \
			> $(TF_DOCS_OUT)/$$m.md; \
	done

uml-frontend: uml-frontend-deps uml-frontend-context

uml-frontend-deps:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" frontend sh -c "mkdir -p /app/site/public/guide/architecture && npx --yes madge --json --extensions ts,tsx --ts-config tsconfig.json app/ lib/ components/ > /app/site/public/guide/architecture/frontend-deps.json"

uml-frontend-context:
	docker compose run --rm -v "$(CURDIR)/site:/app/site" frontend sh -c "node /app/scripts/generate-frontend-context.mjs"

# -----------------------------------------------------------------------
# Infra (infra/terraform/railway/ — 025-iac-provisioning)
#
# Two independent halves, same secrets/*.tfvars source of truth:
#   terraform-*             -> GitHub Actions secrets/variables only (github-ci.tf),
#                             HCP Terraform backend, `terraform` binary on PATH
#                             (local-exec), NOT a container.
#   push/check-railway-variables -> every Railway service's env vars, via the
#                             `railway` CLI + railway-services.json (the community
#                             railway Terraform provider was dropped — its
#                             variable resources are unreliable at this scale).
#
# Credentials: infra/terraform/railway/.env (gitignored, IaC-operator only —
# NOT loaded via the root `include .env`). Template: that dir's .env.example.
#   TF_API_TOKEN / TF_GITHUB_TOKEN                -> terraform (HCP + github provider)
#   RAILWAY_TOKEN_{STAGING,PRODUCTION}            -> push/check/pull-railway-variables
# Every other value comes from secrets/{shared,$(ENV)}.tfvars.
#
# Usage: make terraform-plan ENV=staging (default) | make terraform-apply ENV=production
#        make push-railway-variables ENV=staging
# TARGET= narrows terraform plan/apply to one address (Terraform's -target).
# -----------------------------------------------------------------------

TF_DIR := infra/terraform/railway
TF_ENV_FILE := infra/terraform/railway/.env
ENV ?= staging
# Terraform reads only the GitHub-side tfvars; the railway-*.tfvars are for
# scripts/push_railway_variables.py.
TF_VARFILES := -var-file=secrets/github-shared.tfvars -var-file=secrets/github-$(ENV).tfvars
TF_LOAD_ENV = set -a; test -f $(TF_ENV_FILE) && . $(TF_ENV_FILE); set +a; export TF_WORKSPACE="$(ENV)"; export TF_TOKEN_app_terraform_io="$$TF_API_TOKEN"; export GITHUB_TOKEN="$$TF_GITHUB_TOKEN"; export TF_VAR_github_token="$$TF_GITHUB_TOKEN";
TARGET ?=
_TF_TARGET := $(if $(TARGET),-target=$(TARGET),)
_TF_ENV_GUARD = test "$(ENV)" = staging -o "$(ENV)" = production || (echo "ENV must be 'staging' or 'production' (got '$(ENV)')"; exit 1)

terraform-fmt:
	@terraform -chdir=$(TF_DIR) fmt -check -recursive

terraform-validate:
	@$(TF_LOAD_ENV) terraform -chdir=$(TF_DIR) init -input=false -backend=false >/dev/null && terraform -chdir=$(TF_DIR) validate

terraform-plan:
	@$(_TF_ENV_GUARD)
	@$(TF_LOAD_ENV) terraform -chdir=$(TF_DIR) init -input=false && terraform -chdir=$(TF_DIR) plan $(TF_VARFILES) $(_TF_TARGET)

terraform-apply:
	@$(_TF_ENV_GUARD)
	@$(TF_LOAD_ENV) terraform -chdir=$(TF_DIR) init -input=false && terraform -chdir=$(TF_DIR) apply $(TF_VARFILES) $(_TF_TARGET)

terraform-drift-check:
	@$(_TF_ENV_GUARD)
	@$(TF_LOAD_ENV) terraform -chdir=$(TF_DIR) init -input=false; \
	terraform -chdir=$(TF_DIR) plan $(TF_VARFILES) -detailed-exitcode -no-color; code=$$?; \
	if [ $$code -eq 0 ]; then echo "[$(ENV)] in sync — no drift"; \
	elif [ $$code -eq 2 ]; then echo "[$(ENV)] DRIFT DETECTED — see plan output above"; \
	else echo "[$(ENV)] terraform plan failed (exit $$code)"; exit $$code; fi

# Sync the six git-ignored secrets/{github,railway}-{shared,staging,production}.tfvars
# to GitHub Actions secrets (TF_TFVARS_GITHUB_SHARED / _RAILWAY_STAGING / ...,
# base64) so .github/workflows/terraform.yml can materialize them at apply time.
# Run after editing any value. Needs `gh` authenticated with repo secrets:write.
push-tfvars:
	@for layer in github-shared github-staging github-production railway-shared railway-staging railway-production; do \
		f="infra/terraform/railway/secrets/$$layer.tfvars"; \
		test -f "$$f" || { echo "missing $$f — copy from $$f.example and fill in"; exit 1; }; \
		up=$$(echo "$$layer" | tr 'a-z-' 'A-Z_'); \
		base64 -w0 < "$$f" 2>/dev/null | gh secret set "TF_TFVARS_$$up" || \
		base64 < "$$f" | tr -d '\n' | gh secret set "TF_TFVARS_$$up"; \
		echo "set TF_TFVARS_$$up from $$f"; \
	done

# Recover from a stale state lock (e.g. an interrupted plan/apply never
# released it) — the LOCK ID is printed in the "Error acquiring the state
# lock" message. Only safe when no other terraform operation against this
# workspace is actually still running.
# Usage: make terraform-force-unlock ENV=staging LOCK_ID=<id>
LOCK_ID ?=
terraform-force-unlock:
	@test -n "$(LOCK_ID)" || (echo "LOCK_ID must be set — copy it from the 'Error acquiring the state lock' message"; exit 1)
	@$(TF_LOAD_ENV) terraform -chdir=$(TF_DIR) force-unlock -force $(LOCK_ID)

# Push every Railway service's env vars from secrets/{shared,ENV}.tfvars via the
# `railway` CLI (structure = infra/terraform/railway/railway-services.json). One
# batched `railway variables --set --skip-deploys` per service, then one redeploy.
# Host-only: needs `railway` CLI. Token = gh_env_railway_token from
# secrets/github-$(ENV).tfvars (gh_env_railway_token). Stdlib python.
# Usage: make push-railway-variables ENV=staging [SERVICES="dashboard_backend fastembed"] [NO_REDEPLOY=1] [PRUNE=1]
#   PRUNE=1 also DELETEs Railway vars not in the manifest/tfvars (RAILWAY_* and
#   railway-services.json's `unmanaged`/`unmanaged_all` lists are always kept).
SERVICES ?=
NO_REDEPLOY ?=
PRUNE ?=
push-railway-variables:
	@$(_TF_ENV_GUARD)
	@python scripts/push_railway_variables.py --env $(ENV) $(if $(NO_REDEPLOY),--no-redeploy,) $(if $(PRUNE),--prune,) $(SERVICES)

# Same, read-only: diff live Railway vars vs what the manifest+tfvars say. Exit 2 on drift.
# Usage: make check-railway-variables ENV=staging
check-railway-variables:
	@$(_TF_ENV_GUARD)
	@python scripts/push_railway_variables.py --env $(ENV) --check $(SERVICES)

# Read-only inventory of every service's CURRENT live variable values into
# infra/terraform/railway/.live-variables.json (AS_TFVARS=1 also writes a
# paste-ready draft). Host-only; stdlib python. NOT via docker.
# Usage: make pull-railway-variables [AS_TFVARS=1] [SERVICES="dashboard_backend fastembed"]
AS_TFVARS ?=
pull-railway-variables:
	@python scripts/pull_railway_variables.py $(if $(AS_TFVARS),--as-tfvars,) $(SERVICES)

# ---------------------------------------------------------------------------
# Railway IaC (.railway/railway.ts + `railway config`) — the Windows CLI can't
# evaluate the .ts config, so everything runs in the `railway_cli` container
# (Node + Railway CLI; .railway/Dockerfile; compose profile `tools`).
#
# AUTH — `railway config` needs a Railway PROJECT token (same as the
# `railwayapp/config` GitHub Action). A project token is bound to ONE environment
# and `railway config` resolves which env to plan/apply FROM the token — so the
# slot you fill must hold a token for that env. Put one per env in
# infra/terraform/railway/.env:
#     RAILWAY_TOKEN_STAGING=...        RAILWAY_TOKEN_PRODUCTION=...
# (Railway dashboard → project → Settings → Tokens → New Token → pick the env.)
# The targets read RAILWAY_TOKEN_<ENV> (falling back to a bare RAILWAY_TOKEN in
# the same file) and pass it as `-e RAILWAY_TOKEN=` into the container for that
# one command — nothing is baked into the image. The `make railway-cli` shell
# stays token-free so `railway login --browserless` / `railway link` work there
# (state persists in the /root/.railway volume); if no token resolves, the
# targets fall back to that persisted login. Confirm a token's env with
# `railway status` inside `make railway-cli`.
#
# Each target is DUAL-MODE: on the host it resolves the token and re-invokes
# itself inside the container; in the container (RAILWAY_CLI=1, set by compose)
# it runs `railway` directly against whatever RAILWAY_TOKEN was injected.
#
#   make railway-cli                         # token-free shell (railway login / link here)
#   make railway-config-plan  ENV=staging    # preview — safe, changes nothing
#   make railway-config-plan  ENV=production
#   make railway-config-apply ENV=staging    # apply (interactive confirm)
#   make railway-config-pull  ENV=staging    # fresh ground truth -> .railway/pulled.staging.ts
#                                            #   (your .railway/railway.ts is left untouched)
#   make railway-config-migrate              # fold every railway.toml into .railway/railway.ts
#
# Extra flags: ARGS="--out railway-plan.json"
# ---------------------------------------------------------------------------
ARGS ?=
_RC_UC := $(shell printf '%s' '$(ENV)' | tr '[:lower:]' '[:upper:]')
# Host side: read RAILWAY_TOKEN_<ENV> from infra/terraform/railway/.env and pass
# it to `docker compose run` as -e RAILWAY_TOKEN (only if non-empty). No bare
# RAILWAY_TOKEN fallback — that value's environment is ambiguous and `railway
# config` has no --environment flag, so a wrong token = a wrong-env apply. If the
# var is empty the command uses the persisted `railway login` session in the
# /root/.railway volume against WHATEVER `railway link` last selected — run
# `railway status` in `make railway-cli` to confirm it matches ENV.
_RC_RUN = tok=$$(set -a; . $(TF_ENV_FILE) 2>/dev/null; set +a; printenv RAILWAY_TOKEN_$(_RC_UC) 2>/dev/null || true); \
	test -n "$$tok" && echo "→ auth: RAILWAY_TOKEN_$(_RC_UC) from $(TF_ENV_FILE)" || echo "→ auth: persisted 'railway login' session (ENV=$(ENV) not enforced — check 'railway status')"; \
	docker compose run --rm -it $${tok:+-e RAILWAY_TOKEN=$$tok} railway_cli make
# In-container: the genuine CLI carries the IaC engine, but if a `railway` npm SDK
# ever lands in node_modules it gets used instead and its version self-check runs
# `$$_  --version` — which under make/sh is not `railway`. Pin `_` so that check
# (harmlessly) sees the real CLI.
_RC_EXEC := env _=/usr/local/bin/railway railway

railway-cli:
	@docker compose run --rm -it railway_cli bash

railway-config-plan:
	@$(_TF_ENV_GUARD)
ifdef RAILWAY_CLI
	@$(_RC_EXEC) config plan $(ARGS)
else
	@$(_RC_RUN) railway-config-plan ENV=$(ENV) ARGS='$(ARGS)'
endif

railway-config-apply:
	@$(_TF_ENV_GUARD)
ifdef RAILWAY_CLI
	@$(_RC_EXEC) config apply $(ARGS)
else
	@$(_RC_RUN) railway-config-apply ENV=$(ENV) ARGS='$(ARGS)'
endif

railway-config-pull:
	@$(_TF_ENV_GUARD)
ifdef RAILWAY_CLI
	@cp .railway/railway.ts .railway/.railway.ts.keep && \
	 $(_RC_EXEC) config pull $(ARGS) && \
	 mv .railway/railway.ts .railway/pulled.$(ENV).ts && \
	 mv .railway/.railway.ts.keep .railway/railway.ts && \
	 echo "wrote .railway/pulled.$(ENV).ts — diff it against .railway/railway.ts"
else
	@$(_RC_RUN) railway-config-pull ENV=$(ENV) ARGS='$(ARGS)'
endif

railway-config-migrate:
ifdef RAILWAY_CLI
	@$(_RC_EXEC) config migrate $(ARGS)
else
	@$(_RC_RUN) railway-config-migrate ENV=$(ENV) ARGS='$(ARGS)'
endif

