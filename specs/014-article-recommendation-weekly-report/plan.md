# Implementation Plan: Article Recommendation Signals & Weekly Summary Report

**Branch**: `014-article-recommendation-weekly-report` | **Date**: 2026-06-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-article-recommendation-weekly-report/spec.md`

## Summary

Add article recommendation signals — an extensible, maintainer-curated catalog of academic metrics (citation count now, impact factor/h-index later) refreshed daily via a dedicated cron job, plus view count via Redis — to the existing scrape-analyze pipeline, expose them in the frontend with sort support, and build a weekly LLM-generated summary report system with cover image generation (Gemini Imagen → Cloudflare R2), per-user topic subscriptions, and multi-channel notifications (in-app, email via Resend, Telegram per-user).

**2026-07-12 revision**: The original single hardcoded `citation_count` column (populated only at scrape time, never refreshed) is replaced with a normalized `metric_definitions` (catalog) + `article_metric_values` (per-article values) design, plus a new recurring `refresh_metrics.py` cron job independent of the view_count Redis-flush path. See research.md §9b–§9f and data-model.md for the full design. Only the article-metrics slice of this plan changes; weekly reports, subscriptions, notifications, favorites, and the multimodal LLM provider are unaffected.

## Technical Context

**Language/Version**: Python 3.11 (backend/scraper), TypeScript/React 19 (frontend)

**Primary Dependencies**:
- Existing: FastAPI, SQLAlchemy 2, Alembic, redis-py, structlog, google-generativeai, NextAuth v4, Shadcn/UI, Tailwind CSS v4
- New: `boto3` (Cloudflare R2 via S3-compatible API), `resend` (email notifications), `google-genai` (Imagen 3), `jmespath` (declarative metric-value extraction — see research.md §9c)

**Storage**: PostgreSQL 15 + pgvector (existing), Redis (existing, already in docker-compose), Cloudflare R2 (new — blob storage for weekly report cover images)

**Testing**: pytest (unit + integration), Vitest + Playwright (frontend)

**Target Platform**: Railway (CD), Docker Compose (local dev)

**Project Type**: Web service (FastAPI backend + Next.js frontend + scraper service)

**Performance Goals**: View count increment `<10ms` (Redis write); article list sort `<500ms p95` (SQL JOIN on indexed columns); weekly report generation `<5 min` per topic (LLM + image gen)

**Constraints**: 
- Must follow hexagonal DDD architecture (Constitution §I)
- Redis already deployed; no new infrastructure beyond R2
- All tests must run inside Docker (Constitution §III)
- Image generation deferred gracefully if R2/Imagen unavailable (cover_image_url = null)
- Metric extraction MUST NOT execute arbitrary stored code (FR-023) — declarative JMESPath or a fixed in-code registry only
- Metric catalog (`metric_definitions`) MUST NOT be editable via any runtime/admin API (FR-022) — migration-only

**Scale/Scope**: 
- ~1,000 articles per topic per week (existing scrape volume)
- 1 Alembic migration (23) covering all new tables + model changes
- 7 new DB tables (`article_metrics`, `metric_definitions`, `article_metric_values`, `weekly_reports`, `user_topic_subscriptions`, `user_notification_settings`, `user_article_favorites`), 2 expression indexes on `articles.metadata`, 1 modified model (`llm_providers`)
- 1 new scraper module (`weekly_report`), 2 new entrypoints (`weekly_main.py`, `refresh_metrics.py`)
- ~8 new backend endpoints, ~5 new frontend components (no new frontend surface from the metrics-catalog rework itself — same `citation_count` field shape, different backend sourcing)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| §I DDD — hexagonal architecture | ✅ PASS | Weekly report artifacts added inside existing `intelligence` bounded context — no new top-level module. `ArticleMetrics` domain signals integrated into `collection` module via `ScrapedArticle` value object extension. New `MetricExtractor` domain interface + `ResilientMetricsService`/`JsonPathMetricExtractor` infrastructure impl also live in `collection` (domain/infrastructure split maintained), mirroring the existing `LLMService`/`ResilientLLMService` pattern rather than inventing a new convention. |
| §II Atomic Frontend — component hierarchy | ✅ PASS | `WeeklyReportWidget` goes in `components/features/weekly-report/`. All Storybook stories required. Sort control added to existing `filter-bar.tsx` (no new common component). |
| §III Test Discipline — mandatory tests | ✅ PASS | Test tasks included for all layers: unit tests for weekly_report use case and image service, integration tests for new endpoints, E2E for sort and weekly report widget. |
| §IV Docker-first — service architecture | ✅ PASS | Weekly runner uses existing Docker service (`app`). New Railway Cron Service uses same image. boto3 and resend added to `pyproject.toml`. |
| §V CI-only deployment | ✅ PASS | New Alembic migrations (18–21) auto-run via existing CI migrate job on push to master. |
| §VI Observability | ✅ PASS | Weekly report runner uses structlog. New backend endpoints emit OTel spans. Image upload includes structured logging. |
| §VIII UML conventions | ✅ PASS | New `weekly_report` module follows `src/modules/weekly_report/` structure. Events end in `Event`. Handler exposes `handle()`. |
| §IX FastAPI microservice structure | ✅ PASS | No new microservices. Backend router additions follow existing `backend/routers/` pattern. |

**Post-design re-check**: ✅ All gates pass. Weekly report is placed inside the `intelligence` bounded context (LLM + image generation is its core purpose). Cross-context data access (reading `Article`/`Analysis`/`Tag` entities) is via a read-only `WeeklyReportRepository` interface in `intelligence/domain/repositories/` — implementations query the DB directly without importing `collection` domain types. Metric extraction (`MetricExtractor`, `ResilientMetricsService`) stays inside `collection` (it operates on `Article`/`ScrapedArticle`, not a separate concern) and follows the same domain-interface/infrastructure-impl split already established by `LLMService`/`ResilientLLMService` — no new architectural pattern introduced.

## Complexity Tracking

| Aspect | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|--------------------------------------|
| Separate `article_metrics` table | Different scrapers provide different signals; keeps `articles` hot-path clean | Adding nullable columns to `articles` would widen a critical table and make sort queries require COALESCE everywhere |
| Redis view count with dedup | High-throughput write-path for view tracking | Direct PostgreSQL UPDATE on every view would serialize under concurrent load |
| New `weekly_report` bounded context | Weekly report has its own lifecycle (pending/completed/failed), distinct from article collection | Placing in `collection` module would violate single-responsibility; weekly reports are not scraped articles |
| Cloudflare R2 (external blob storage) | Railway has no native S3; weekly report images are 1-4MB blobs unsuitable for PostgreSQL | Base64 in PostgreSQL is not production-appropriate for binary assets |
| 3-channel notification (in-app + email + Telegram) | User explicitly requested all three | In-app only would miss users who don't visit; email alone misses Telegram preference |
| Separate `metric_definitions` + `article_metric_values` tables instead of a `citation_count` column or a `metrics JSONB` blob | New academic signals (impact factor, h-index, etc.) will be added over time; a hardcoded column per metric doesn't scale (every addition = migration + scraper code change), and a JSONB blob can't be indexed per-key for sort/ranking queries | A `metrics JSONB` column on `article_metrics` was considered and rejected — un-indexable per key without generated columns, and mixes backend-owned usage signals with src-owned academic signals in one table (see research.md §9b) |
| `metric_definitions` is migration-only, no admin/dashboard UI (FR-022) | Letting deployment admins define arbitrary provider-response field mappings was evaluated and rejected as a self-service dashboard feature — the UX cost (surfacing each provider's response shape, building a mapping editor) outweighed the low frequency of "add a new metric" as an operation | A full self-service dashboard (admin defines new metrics + extraction rules at runtime) was the alternative; rejected for UX cost and because extraction-as-stored-code (the only way to make it fully generic) is a code-execution risk (FR-023) |
| `refresh_metrics.py` as a separate cron job/entrypoint, not reusing `weekly_main.py` or the view_count flush | Citation refresh has different data sources (external academic APIs) and cadence (daily) than both the weekly report (weekly, LLM-driven) and view_count (Redis, near-real-time); forcing them to share a runner would couple unrelated failure domains | Extending `weekly_main.py` to also refresh metrics was considered — rejected because a citation-fetch failure would then also risk blocking/delaying report generation, and the schedules (daily vs weekly) don't naturally coincide |

## Project Structure

### Documentation (this feature)

```text
specs/014-article-recommendation-weekly-report/
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── data-model.md        # Entity definitions and SQL schemas
├── quickstart.md        # Dev setup and manual trigger guide
├── contracts/
│   └── api.md           # REST endpoint contracts
└── tasks.md             # Phase 2 output (speckit-tasks command)
```

### Source Code (repository root)

```text
# Backend (FastAPI)
backend/
├── routers/
│   ├── articles.py         # extend: citation_count/view_count in ArticleOut, POST /articles/{id}/view, sort by new fields
│   ├── weekly_reports.py   # new: GET /weekly-reports, GET /weekly-reports/latest
│   └── user.py             # new: GET|PUT /user/notification-settings, GET|POST|DELETE /user/subscriptions/{topic_id}
├── schemas/
│   ├── article.py          # extend ArticleOut + ArticleDetailOut with citation_count, view_count
│   └── weekly_report.py    # new: WeeklyReportOut
└── services/
    ├── article_service.py  # extend: JOIN article_metrics (view_count) + article_metric_values (citation_count, filtered metric_key='citation_count') for sort + output; view count flush logic unchanged
    └── weekly_report_service.py  # new: get_weekly_reports, get_latest_weekly_report

# Scraper service (DDD)
src/
├── modules/
│   ├── collection/
│   │   └── domain/
│   │       ├── value_objects/scraped_article.py       # revise: citation_count field → metric_seeds: Dict[str, Any]
│   │       ├── repositories/article_metrics_repository.py  # revise: upsert(article_id, citation_count) → upsert(article_id, metrics: dict)
│   │       └── services/metric_extractor.py            # new: MetricExtractor domain interface (fetch/extract)
│   └── intelligence/                              # weekly report lives here, not a separate bounded context
│       ├── domain/
│       │   ├── entities/
│       │   │   └── weekly_report.py               # new
│       │   ├── repositories/
│       │   │   └── weekly_report_repository.py    # new: interface
│       │   ├── services/
│       │   │   ├── image_generation_service.py    # new: interface
│       │   │   └── blob_storage_service.py        # new: interface (R2 impl in infrastructure)
│       │   └── value_objects/
│       │       ├── article_summary_for_report.py  # new: per-article prompt input DTO
│       │       ├── weekly_report_prompt.py        # new: extends BasePrompt
│       │       └── image_generation_prompt.py     # new: extends BasePrompt
│       └── application/
│           └── use_cases/
│               └── generate_weekly_report.py      # new
├── infrastructure/
│   ├── collection/
│   │   ├── scrapers/
│   │   │   ├── openalex_scraper.py     # extend: populate metric_seeds={"citation_count": ...} on ScrapedArticle
│   │   │   └── semantic_scholar_scraper.py  # extend: same, metric_seeds
│   │   ├── clients/
│   │   │   ├── openalex_client.py           # new method: fetch_by_doi(doi) -> Optional[dict] (raw JSON, for refresh job)
│   │   │   └── semantic_scholar_client.py    # new method: fetch_by_doi(doi) -> Optional[dict]
│   │   └── metrics/                          # new subpackage
│   │       ├── json_path_extractor.py        # new: JsonPathMetricExtractor (jmespath-based, generic)
│   │       └── resilient_metrics_service.py  # new: ResilientMetricsService (mirrors ResilientLLMService)
│   ├── persistence/
│   │   └── collection/
│   │       └── article_metrics_repo_impl.py  # revise: upsert() writes N rows to article_metric_values instead of 1 column
│   ├── intelligence/
│   │   ├── image/
│   │   │   ├── base_image_provider.py         # new
│   │   │   └── gemini_imagen_provider.py      # new
│   │   └── repositories/
│   │       └── weekly_report_repo_impl.py     # new
│   └── storage/
│       └── r2_blob_storage.py          # new
└── entrypoints/
    └── cli/
        ├── weekly_main.py    # new: weekly runner entrypoint (validates multimodal provider on startup)
        └── refresh_metrics.py  # new: daily metric-refresh runner — queries stale article_metric_values, runs ResilientMetricsService, upserts

# Shared (importable by both src/ and backend/, no src. prefix — see shared/llm_provider.py for the established pattern)
shared/
└── metric_definition.py  # new: load_enabled_metric_definitions(session) -> List[Dict[str, Any]], mirrors load_active_providers()

# ORM Models (shared)
models/
├── article_metrics.py          # revise: remove citation_count column, keep view_count only
├── metric_definition.py        # new
├── article_metric_value.py     # new
├── weekly_report.py            # new
└── user_subscription.py        # new: UserTopicSubscription + UserNotificationSettings + UserArticleFavorite

# Alembic migrations
alembic/versions/
└── 23_article_recommendation_weekly_report.py  # all new tables (incl. metric_definitions + article_metric_values + seed data + articles.metadata expression indexes) + llm_provider type column

# Frontend
frontend/
├── app/
│   └── page.tsx                    # extend: add WeeklyReportWidget above InlineQABarWrapper
├── components/
│   └── features/
│       ├── articles/
│       │   ├── article-card.tsx             # extend: heart icon (left of title), citation_count badge, view_count, fire view event
│       │   ├── article-detail-dialog.tsx    # extend: citation_count + view_count display
│       │   └── filter-bar.tsx               # extend: sort dropdown on right + Favorites toggle
│       └── weekly-report/                   # new feature directory
│           ├── weekly-report-widget.tsx
│           ├── weekly-report-skeleton.tsx
│           └── weekly-report-widget.stories.tsx  # required by Constitution §II
└── lib/
    └── api/
        ├── articles.ts             # extend: recordArticleView(), update types (citation_count, view_count, is_favorited)
        ├── weekly-reports.ts       # new
        └── user.ts                 # new or extend: subscriptions, notification settings, favorites (addFavorite, removeFavorite, getFavorites)
```

**Structure Decision**: Web application (Option 2). Feature touches all three service layers: `src/` (scraper/DDD), `backend/` (FastAPI), and `frontend/` (Next.js). Weekly report generation is an application of LLM + image generation and belongs inside the existing `intelligence` bounded context — no new top-level module is created.

## Implementation Phases

### Phase A: Data Foundation (Migrations + Models)
1. Create single Alembic migration `23_article_recommendation_weekly_report.py` — all new tables (including `metric_definitions` with seed data, `article_metric_values`, two `articles.metadata` expression indexes) + `type` column on `llm_providers`
2. Create ORM models: `article_metrics.py` (view_count only), `metric_definition.py`, `article_metric_value.py`, `weekly_report.py`, `user_subscription.py`
3. Extend `LlmProvider` model to add `CheckConstraint` for `type IN ('llm', 'embedding', 'multimodal')` and fix duplicate `type` column definition
4. Create `shared/metric_definition.py::load_enabled_metric_definitions(session)`, mirroring `shared/llm_provider.py::load_active_providers`

### Phase B: Article Metrics Collection (opportunistic seed path)
1. Revise `ScrapedArticle` value object: `citation_count` field → `metric_seeds: Dict[str, Any]`
2. Revise `openalex_scraper.py` and `semantic_scholar_scraper.py` to populate `metric_seeds={"citation_count": ...}`
3. Revise `ArticleMetricsRepository.upsert()` signature to `upsert(article_id, metrics: dict[str, Any])`; `SqlAlchemyArticleMetricsRepository` writes to `article_metric_values` (`INSERT ... ON CONFLICT (article_id, metric_key) DO UPDATE`)
4. Revise `ProcessScrapedArticleUseCase` to forward `metric_seeds` (filtered to known `metric_definitions.metric_key` values) to the generalized `upsert()`
5. Extend backend `ArticleOut` schema and `get_articles_paginated` to JOIN `article_metrics` (view_count) + `article_metric_values` (citation_count via `metric_key='citation_count'` filter)
6. Add `citation_count` and `view_count` to sort options in `GET /articles` (sort now joins `article_metric_values`, not a flat column)

### Phase B2: Recurring Metric Refresh (new)
1. Add `fetch_by_doi()` (raw-JSON-returning) to `OpenAlexClient` and `SemanticScholarClient` — new methods, `fetch_papers()` unchanged
2. Create `MetricExtractor` domain interface (`src/modules/collection/domain/services/metric_extractor.py`)
3. Create `JsonPathMetricExtractor` (`src/infrastructure/collection/metrics/json_path_extractor.py`) using `jmespath`
4. Create `ResilientMetricsService` (`src/infrastructure/collection/metrics/resilient_metrics_service.py`), built at bootstrap from `load_enabled_metric_definitions()` — priority-ordered fallback per `metric_key`, mirrors `ResilientLLMService`
5. Wire `build_metrics_refresh_pipeline()` in `src/bootstrap.py`
6. Create `src/entrypoints/cli/refresh_metrics.py`: query articles with a missing or stale (`last_flushed_at < now() - interval '1 day'`) row for each enabled `metric_key` (via the `articles.metadata` DOI/arxiv_id expression indexes), call `ResilientMetricsService.fetch_all()`, upsert results
7. Add Railway Cron Service entry for `refresh_metrics.py` in `src/railway.toml` (daily), reusing `src/Dockerfile`
8. Update `WeeklyReportRepoImpl`'s article-selection query and `ArticleSummaryForReport` sourcing to join `article_metric_values` instead of the old `am.citation_count` column

### Phase C: View Count Tracking
1. Add `POST /articles/{id}/view` backend endpoint (Redis INCR with IP dedup)
2. Add admin `POST /admin/articles/flush-view-counts` to trigger DB sync
3. Add background flush task (periodic, configurable interval via env var)
4. Frontend: fire `recordArticleView(id)` when `ArticleDetailDialog` opens

### Phase D: Frontend Metrics Display + Sort
1. Extend `ArticleCard` with citation_count badge and view_count badge
2. Extend `ArticleDetailDialog` with citation_count and view_count
3. Extend `FilterBar` with sort dropdown (right side, immediate apply, no draft state)
4. Update `useArticles` hook / articles page to pass sort params to API

### Phase E: Weekly Report Infrastructure
1. Add weekly report domain artifacts inside existing `intelligence` module: `WeeklyReport` entity, `WeeklyReportRepository` interface, `ImageGenerationService` interface, `BlobStorageService` interface, `ArticleSummaryForReport` value object, `WeeklyReportPrompt`, `ImageGenerationPrompt`
2. Create `GeminiImagenProvider` implementing `ImageGenerationService` (`src/infrastructure/intelligence/image/`)
3. Create `R2BlobStorageService` (`src/infrastructure/storage/`)
4. Create `WeeklyReportRepoImpl` (`src/infrastructure/intelligence/repositories/`)
5. Create `GenerateWeeklyReportUseCase` (`src/modules/intelligence/application/use_cases/generate_weekly_report.py`)
6. Wire in `src/bootstrap.py` via new `build_weekly_pipeline()` function
7. Create `src/entrypoints/cli/weekly_main.py` — on startup queries DB for active `type='multimodal'` provider; exits with clear error if none found

### Phase F: Notification Pipeline
1. Extend `user_notification_settings` query to identify subscribed users per topic
2. Create `WeeklyReportEmailNotifier` (uses Resend SDK)
3. Create `WeeklyReportTelegramNotifier` (parameterized chat_id, reuse request pattern)
4. Integrate notifications into `GenerateWeeklyReportUseCase` post-generation
5. Add `providers.toml` entry for Imagen provider

### Phase G: Backend API for Reports + Subscriptions
1. Create `backend/routers/weekly_reports.py` (`GET /weekly-reports`, `GET /weekly-reports/latest`)
2. Create `backend/routers/user.py` (subscription + notification settings endpoints)
3. Create `backend/schemas/weekly_report.py`
4. Register new routers in `backend/main.py`

### Phase H: Frontend Weekly Report Widget + Homepage
1. Create `WeeklyReportWidget`, `WeeklyReportSkeleton` components
2. Create Storybook stories for both (Constitution §II requirement)
3. Update `app/page.tsx` to show `WeeklyReportWidget` above `InlineQABarWrapper`
4. Create `frontend/lib/api/weekly-reports.ts`

### Phase I: Settings UI (Subscriptions + Notification Preferences)
1. Add subscription management UI to existing settings page
2. Add notification settings form (email toggle, Telegram chat_id input)
3. Connect to new API endpoints

### Phase J: Tests
1. Unit tests: `WeeklyReportUseCase`, `GeminiImagenProvider`, `R2BlobStorageService`, view count flush
2. Unit tests: `JsonPathMetricExtractor` (jmespath evaluation against fixture responses), `ResilientMetricsService` fallback ordering, generalized `ArticleMetricsRepository.upsert()`, `refresh_metrics.py` staleness query
3. Backend integration tests: new endpoints (weekly reports, subscriptions, view count), `GET /articles` sort/citation_count join against `article_metric_values`
4. Frontend unit tests: `WeeklyReportWidget`, sort in `FilterBar`
5. E2E: sort articles by citation_count, weekly report widget display

## Environment Variables Summary

New variables to add to `.env.example`:

```bash
# Cloudflare R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=

# Email (Resend)
RESEND_API_KEY=
RESEND_FROM_EMAIL=

# Optional: separate API key for Imagen (defaults to GEMINI_API_KEY)
IMAGEN_API_KEY=

# View count flush interval (seconds, default 900 = 15 min)
VIEW_COUNT_FLUSH_INTERVAL=900
```

## Dependencies to Add

```toml
# pyproject.toml (core group)
boto3 = ">=1.34"
resend = ">=2.0"

# google-genai (for Imagen 3) — check if google-generativeai already covers this
# If using newer google-genai package:
# google-genai = ">=0.8"

# pyproject.toml (scraper group) — declarative metric extraction (research.md §9c)
jmespath = ">=1.0"
```
