# alloy

Grafana Alloy service that ships Postgres metrics to Grafana Cloud Prometheus:
the embedded `postgres_exporter` (`prometheus.exporter.postgres`) reads Postgres's
statistics views — `pg_stat_statements`, `pg_stat_user_tables`,
`pg_statio_user_indexes`, locks, database size, … — and Alloy remote-writes them,
labelled `env="staging|production"`, `job="integrations/postgres_exporter"`.

- `config.alloy` — the pipeline (exporter → scrape every 60s → remote_write)
- `queries.yaml` — custom exporter queries for what the built-in collectors miss:
  `pg_stat_user_indexes_{idx_scan,idx_tup_read,idx_tup_fetch,size_bytes}` per index
  (e.g. `pg_stat_user_indexes_idx_scan == 0` finds indexes nothing ever uses)
- `Dockerfile` — `grafana/alloy` pinned, config baked in
- Deployed as the `alloy` Railway service (`.railway/railway.ts`), both environments.
  No public domain; its debug UI listens on `:12345` on the private network only.

## Database role

The exporter connects as `alloy_monitor`, a read-only role that can see every
statistics view but no table data. Created once per environment, by hand (Railway's
managed Postgres is hands-off for IaC — FR-014), as the `postgres` superuser:

```sql
CREATE ROLE alloy_monitor WITH LOGIN PASSWORD '<openssl rand -hex 32>' CONNECTION LIMIT 3;
GRANT pg_monitor TO alloy_monitor;
ALTER ROLE alloy_monitor SET default_transaction_read_only = on;
ALTER ROLE alloy_monitor SET statement_timeout = '5s';
GRANT CONNECT ON DATABASE railway TO alloy_monitor;
```

The password goes in `infra/terraform/github/secrets/railway-{staging,production}.tfvars`
as `alloy_pg_password` (then `make push-tfvars`). It is spliced into a connection URL
unencoded, so keep it URL-safe — the hex form above is.

## Environment variables

Set by `.railway/railway.ts`:

| Variable | Source |
|---|---|
| `POSTGRES_EXPORTER_DSN` | built from `ALLOY_PG_PASSWORD` + `${{Postgres.*}}` references |
| `ALLOY_PG_PASSWORD` | tfvars `alloy_pg_password` |
| `GRAFANA_PROMETHEUS_URL`, `GRAFANA_PROMETHEUS_USER` | `.railway/constants.ts` |
| `GRAFANA_API_KEY` | tfvars `grafana_api_key` (needs `metrics:write`) |
| `APP_ENV` | `staging` / `production` |

## Local check

```bash
docker build -f alloy/Dockerfile -t alloy-local .
docker run --rm --network scrape-analyzer_default -p 12345:12345 \
  -e POSTGRES_EXPORTER_DSN="postgresql://postgres:postgres@postgres:5432/postgres?sslmode=disable" \
  -e GRAFANA_PROMETHEUS_URL=http://127.0.0.1:1/api/prom -e GRAFANA_PROMETHEUS_USER=x \
  -e GRAFANA_API_KEY=x -e APP_ENV=local alloy-local
# http://localhost:12345 — component health; the exporter's raw metrics at
# /api/v0/component/prometheus.exporter.postgres.db/metrics
```

The local Postgres doesn't preload `pg_stat_statements`, so the `stat_statements`
collector logs an error there; Railway's Postgres has it.
