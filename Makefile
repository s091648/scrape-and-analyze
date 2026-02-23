.PHONY: migrate dump sync

# load environment file so targets can see variables like REMOTE_RAILWAY_DB_URL
ifneq (,$(wildcard .env))
include .env
export
endif

# default remote URL uses the variable from .env if present
REMOTE_URL ?= $(REMOTE_RAILWAY_DB_URL)
DUMP_FILE ?= /app/railway_dump.sql

migrate:
	docker compose run --rm job_service /app/scripts/db_migrate.sh

# dump the remote database into the shared volume (default /app/railway_dump.sql)
dump:
	@echo "remote url = $(REMOTE_URL)"
	@test -n "$(REMOTE_URL)" || (echo "REMOTE_URL must be set"; exit 1)
	docker compose run --rm -e RAILWAY_DATABASE_URL="$(REMOTE_URL)" \
		job_service /app/scripts/dump_remote.sh "$(REMOTE_URL)" "$(DUMP_FILE)"

# restore last dump file into local postgres
sync:
	@echo "using dump file = $(DUMP_FILE)"
	docker compose run --rm \
		-e PGPASSWORD=$${PGPASSWORD:-digital_twins} \
		job_service /app/scripts/sync_db.sh "$(DUMP_FILE)"
