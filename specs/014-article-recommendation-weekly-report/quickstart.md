# Quickstart: Article Recommendation Signals & Weekly Summary Report

## Prerequisites

- Docker + Docker Compose running (`docker compose up`)
- Existing scrape-analyzer setup complete (migrations through 17 applied)
- API keys: `GEMINI_API_KEY` already set

## New Environment Variables Required

Add to `.env` (and `.env.example`):

```bash
# Cloudflare R2 blob storage (for weekly report cover images)
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=scrape-analyzer-assets
R2_PUBLIC_URL=https://pub-xxx.r2.dev  # or custom domain

# Email notifications (Resend)
RESEND_API_KEY=re_xxx
RESEND_FROM_EMAIL=weekly@yourdomain.com

# Imagen model (if using separate API key from GEMINI_API_KEY)
# If not set, falls back to GEMINI_API_KEY
IMAGEN_API_KEY=
```

## Running Migrations

```bash
# Apply all new migrations (18–21) in sequence
docker compose run --rm job_service make migrate

# Or individually:
docker compose run --rm job_service uv run alembic upgrade 18_article_metrics_table
docker compose run --rm job_service uv run alembic upgrade 19_weekly_reports_table
docker compose run --rm job_service uv run alembic upgrade 20_user_subscription_tables
docker compose run --rm job_service uv run alembic upgrade 21_llm_provider_type_image
```

## Registering the Imagen Provider

Add to `providers.toml`:

```toml
[[providers]]
name = "gemini-imagen"
type = "image"
model = "imagen-3.0-generate-001"
api_key_env = "GEMINI_API_KEY"
priority = 1

[providers.strategy]
type = "sliding_window"
rpm = 2
tpm = 0
rpd = 50
```

## Generating a Weekly Report (Manual)

```bash
# Via admin API (backend must be running)
curl -X POST http://localhost:8000/admin/weekly-reports/generate \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"topic_id": "<uuid>", "week_start_date": "2026-06-22"}'

# Or run the weekly runner directly (Docker):
docker compose run --rm job_service uv run python -m src.entrypoints.cli.weekly_main \
  --topic-id <uuid> --week-start 2026-06-22
```

## Testing View Count Tracking

```bash
# Increment view count for an article
curl -X POST http://localhost:8000/articles/<article-uuid>/view

# Trigger manual flush of Redis view counts to DB
curl -X POST http://localhost:8000/admin/articles/flush-view-counts \
  -H "Authorization: Bearer <admin_jwt>"
```

## Running Tests

```bash
# Unit tests (includes new weekly_report module tests)
make test

# Integration tests (requires postgres + redis)
make test-integration

# Frontend unit tests
cd frontend && npm run test

# Frontend E2E (weekly report widget + sort)
cd frontend && npm run test:e2e
```

## Railway Deployment (Cron Services)

In Railway dashboard, create two Cron Services (independent of each other and of the `app`/backend services — see research.md §9b, §9f):
- **Weekly report**: Command `uv run python -m src.entrypoints.cli.weekly_main`, schedule `0 8 * * 1` (Every Monday at 08:00 UTC)
- **Metric refresh** (new, 2026-07-12): Command `uv run python -m src.entrypoints.cli.refresh_metrics`, schedule `0 3 * * *` (daily at 03:00 UTC — off-peak, ahead of the weekly report's Monday run so citation counts used in Monday's report are fresh)
- **Environment**: Same `.env` variables as `app` service

## Testing Metric Refresh (Manual)

```bash
docker compose run --rm job_service uv run python -m src.entrypoints.cli.refresh_metrics
```

## Architecture Diagram

After implementing, regenerate the UML:
```bash
make uml-backend
```

The weekly_report module will appear as a new bounded context with its own pipeline.
