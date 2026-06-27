# Implementation Plan: Article Recommendation Signals & Weekly Summary Report

**Branch**: `014-article-recommendation-weekly-report` | **Date**: 2026-06-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-article-recommendation-weekly-report/spec.md`

## Summary

Add article recommendation signals (citation count from academic scrapers + view count via Redis) to the existing scrape-analyze pipeline, expose them in the frontend with sort support, and build a weekly LLM-generated summary report system with cover image generation (Gemini Imagen → Cloudflare R2), per-user topic subscriptions, and multi-channel notifications (in-app, email via Resend, Telegram per-user).

## Technical Context

**Language/Version**: Python 3.11 (backend/scraper), TypeScript/React 19 (frontend)

**Primary Dependencies**:
- Existing: FastAPI, SQLAlchemy 2, Alembic, redis-py, structlog, google-generativeai, NextAuth v4, Shadcn/UI, Tailwind CSS v4
- New: `boto3` (Cloudflare R2 via S3-compatible API), `resend` (email notifications), `google-genai` (Imagen 3)

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

**Scale/Scope**: 
- ~1,000 articles per topic per week (existing scrape volume)
- 1 Alembic migration (23) covering all new tables + model changes
- 3 new DB tables, 1 modified model
- 1 new scraper module (`weekly_report`), 1 new entrypoint
- ~8 new backend endpoints, ~5 new frontend components

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| §I DDD — hexagonal architecture | ✅ PASS | Weekly report artifacts added inside existing `intelligence` bounded context — no new top-level module. `ArticleMetrics` domain signals integrated into `collection` module via `ScrapedArticle` value object extension. |
| §II Atomic Frontend — component hierarchy | ✅ PASS | `WeeklyReportWidget` goes in `components/features/weekly-report/`. All Storybook stories required. Sort control added to existing `filter-bar.tsx` (no new common component). |
| §III Test Discipline — mandatory tests | ✅ PASS | Test tasks included for all layers: unit tests for weekly_report use case and image service, integration tests for new endpoints, E2E for sort and weekly report widget. |
| §IV Docker-first — service architecture | ✅ PASS | Weekly runner uses existing Docker service (`app`). New Railway Cron Service uses same image. boto3 and resend added to `pyproject.toml`. |
| §V CI-only deployment | ✅ PASS | New Alembic migrations (18–21) auto-run via existing CI migrate job on push to master. |
| §VI Observability | ✅ PASS | Weekly report runner uses structlog. New backend endpoints emit OTel spans. Image upload includes structured logging. |
| §VIII UML conventions | ✅ PASS | New `weekly_report` module follows `src/modules/weekly_report/` structure. Events end in `Event`. Handler exposes `handle()`. |
| §IX FastAPI microservice structure | ✅ PASS | No new microservices. Backend router additions follow existing `backend/routers/` pattern. |

**Post-design re-check**: ✅ All gates pass. Weekly report is placed inside the `intelligence` bounded context (LLM + image generation is its core purpose). Cross-context data access (reading `Article`/`Analysis`/`Tag` entities) is via a read-only `WeeklyReportRepository` interface in `intelligence/domain/repositories/` — implementations query the DB directly without importing `collection` domain types.

## Complexity Tracking

| Aspect | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|--------------------------------------|
| Separate `article_metrics` table | Different scrapers provide different signals; keeps `articles` hot-path clean | Adding nullable columns to `articles` would widen a critical table and make sort queries require COALESCE everywhere |
| Redis view count with dedup | High-throughput write-path for view tracking | Direct PostgreSQL UPDATE on every view would serialize under concurrent load |
| New `weekly_report` bounded context | Weekly report has its own lifecycle (pending/completed/failed), distinct from article collection | Placing in `collection` module would violate single-responsibility; weekly reports are not scraped articles |
| Cloudflare R2 (external blob storage) | Railway has no native S3; weekly report images are 1-4MB blobs unsuitable for PostgreSQL | Base64 in PostgreSQL is not production-appropriate for binary assets |
| 3-channel notification (in-app + email + Telegram) | User explicitly requested all three | In-app only would miss users who don't visit; email alone misses Telegram preference |

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
    ├── article_service.py  # extend: JOIN article_metrics for sort + output; view count flush logic
    └── weekly_report_service.py  # new: get_weekly_reports, get_latest_weekly_report

# Scraper service (DDD)
src/
├── modules/
│   ├── collection/
│   │   └── domain/
│   │       └── value_objects/scraped_article.py  # extend: add citation_count field
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
│   │   └── scrapers/
│   │       ├── openalex_scraper.py     # extend: pass citation_count through to ScrapedArticle
│   │       └── semantic_scholar_scraper.py  # extend: pass citation_count through
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
        └── weekly_main.py  # new: weekly runner entrypoint (validates multimodal provider on startup)

# ORM Models (shared)
models/
├── article_metrics.py          # new
├── weekly_report.py            # new
└── user_subscription.py        # new: UserTopicSubscription + UserNotificationSettings + UserArticleFavorite

# Alembic migrations
alembic/versions/
└── 23_article_recommendation_weekly_report.py  # all new tables + llm_provider type column

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
│           ├── weekly-report-card.tsx
│           ├── weekly-report-skeleton.tsx
│           ├── weekly-report-widget.stories.tsx  # required by Constitution §II
│           └── weekly-report-card.stories.tsx    # required by Constitution §II
└── lib/
    └── api/
        ├── articles.ts             # extend: recordArticleView(), update types (citation_count, view_count, is_favorited)
        ├── weekly-reports.ts       # new
        └── user.ts                 # new or extend: subscriptions, notification settings, favorites (addFavorite, removeFavorite, getFavorites)
```

**Structure Decision**: Web application (Option 2). Feature touches all three service layers: `src/` (scraper/DDD), `backend/` (FastAPI), and `frontend/` (Next.js). Weekly report generation is an application of LLM + image generation and belongs inside the existing `intelligence` bounded context — no new top-level module is created.

## Implementation Phases

### Phase A: Data Foundation (Migrations + Models)
1. Create single Alembic migration `23_article_recommendation_weekly_report.py` (all new tables + `type` column on `llm_providers`)
2. Create ORM models: `article_metrics.py`, `weekly_report.py`, `user_subscription.py`
3. Extend `LlmProvider` model to add `CheckConstraint` for `type IN ('llm', 'embedding', 'multimodal')` and fix duplicate `type` column definition

### Phase B: Article Metrics Collection
1. Extend `ScrapedArticle` value object with `citation_count`
2. Extend `openalex_scraper.py` and `semantic_scholar_scraper.py` to populate `citation_count`
3. Extend `ProcessScrapedArticleUseCase` to upsert `article_metrics` row after article save
4. Extend backend `ArticleOut` schema and `get_articles_paginated` to JOIN `article_metrics`
5. Add `citation_count` and `view_count` to sort options in `GET /articles`

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
1. Create `WeeklyReportWidget`, `WeeklyReportCard`, `WeeklyReportSkeleton` components
2. Create Storybook stories for both (Constitution §II requirement)
3. Update `app/page.tsx` to show `WeeklyReportWidget` above `InlineQABarWrapper`
4. Create `frontend/lib/api/weekly-reports.ts`

### Phase I: Settings UI (Subscriptions + Notification Preferences)
1. Add subscription management UI to existing settings page
2. Add notification settings form (email toggle, Telegram chat_id input)
3. Connect to new API endpoints

### Phase J: Tests
1. Unit tests: `WeeklyReportUseCase`, `GeminiImagenProvider`, `R2BlobStorageService`, view count flush
2. Backend integration tests: new endpoints (weekly reports, subscriptions, view count)
3. Frontend unit tests: `WeeklyReportWidget`, sort in `FilterBar`
4. E2E: sort articles by citation_count, weekly report widget display

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
```
