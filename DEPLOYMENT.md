# Deployment Guide

## Railway Setup

1. Create a new Railway project
2. Add PostgreSQL database from Railway marketplace
3. Set environment variables:
   - `DATABASE_URL`: Automatically set by Railway PostgreSQL plugin
   - `LLM_API_KEY`: Your Anthropic API key (`sk-ant-...`)
   - `LLM_PROVIDER`: `claude`
   - `LLM_MODEL`: `claude-sonnet-4-20250514`
   - `SENTRY_DSN`: (optional) Sentry DSN for error tracking

## Cron Jobs

Create two cron jobs in Railway:

### Daily Scraper
- Schedule: `0 8 * * *` (8:00 AM UTC daily)
- Command: `python -m src.main daily`

### Weekly Scraper
- Schedule: `0 8 * * 1` (8:00 AM UTC every Monday)
- Command: `python -m src.main weekly`

### Remediation (optional)
- Schedule: `0 9 * * *` (9:00 AM UTC daily, after daily scraper)
- Command: `python -m src.main remediate`

## Database Migrations

Run migrations manually via Railway CLI:

```bash
railway run psql $DATABASE_URL -f migrations/001_initial.sql
```

Or connect directly:

```bash
railway connect postgres
\i migrations/001_initial.sql
```

## Local Development

```bash
# Start local stack
docker compose up -d

# Run unit tests
docker compose exec app python -m pytest tests/unit/ -v

# Run integration tests
docker compose exec app python -m pytest tests/integration/ -v -m integration

# Dry-run daily scrape locally
docker compose exec app python -m src.main daily
```

## Verification

1. Check Railway logs for structured JSON output from each run
2. Query database to verify articles and analyses are being created:
   ```sql
   SELECT COUNT(*) FROM articles;
   SELECT COUNT(*) FROM analyses;
   SELECT COUNT(*) FROM failed_tasks WHERE resolved = false;
   ```
3. Monitor Sentry Dashboard for errors (if `SENTRY_DSN` is configured)

## Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string (auto-set by Railway) |
| `LLM_API_KEY` | Yes | — | Anthropic API key |
| `LLM_PROVIDER` | No | `claude` | LLM provider name |
| `LLM_MODEL` | No | `claude-sonnet-4-20250514` | Claude model ID |
| `SENTRY_DSN` | No | `""` | Sentry DSN for error tracking |
