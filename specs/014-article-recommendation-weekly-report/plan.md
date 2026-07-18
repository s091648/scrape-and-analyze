# Implementation Plan: Article Recommendation Signals & Weekly Summary Report

**Branch**: `014-article-recommendation-weekly-report` | **Date**: 2026-06-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-article-recommendation-weekly-report/spec.md`

## Summary

Add article recommendation signals — an extensible, maintainer-curated catalog of academic metrics (citation count now, impact factor/h-index later) refreshed daily via a dedicated cron job, plus view count via Redis — to the existing scrape-analyze pipeline, expose them in the frontend with sort support, and build a weekly LLM-generated summary report system with cover image generation (Gemini Imagen → Cloudflare R2), per-user topic subscriptions, and multi-channel notifications (in-app, email via Resend, Telegram per-user).

**2026-07-12 revision**: The original single hardcoded `citation_count` column (populated only at scrape time, never refreshed) is replaced with a normalized `metric_definitions` (catalog) + `article_metric_values` (per-article values) design, plus a new recurring `refresh_metrics.py` cron job independent of the view_count Redis-flush path. See research.md §9b–§9f and data-model.md for the full design. Only the article-metrics slice of this plan changes; weekly reports, subscriptions, notifications, favorites, and the multimodal LLM provider are unaffected.

**2026-07-12 addition — User Story 6 (paragraph-level citations, FR-024–FR-029)**: Weekly report summaries gain inline `[N]` citation markers pointing to the specific articles a claim draws on, reusing the chat feature's existing citation UX. This also fixes a pre-existing bug where `WeeklyReport.article_ids` was populated with article title strings instead of real UUIDs, making citation resolution (and any future per-article linkage) impossible. See Phase K below; no new bounded context or service.

**2026-07-12 addition — User Story 7 (pin report into chat, FR-030–FR-034)**: The weekly report widget gains a report-level pin control that bulk-adds the report's cited articles (Feature 1's `sources`) into the existing shared `usePinnedArticle` context. The homepage's `InlineQABarWrapper` — which currently has zero pinning support, unlike the separate `FloatingChatbotWrapper` — gains the same `X-Pinned-Article-Ids` header forwarding and a visible pinned-chip row. No backend or `chatbot-plugin` RAG changes: pinned-article retrieval is already implemented as a filtered vector search keyed by article id (`ChatService._fetch_pinned_chunks()`), and this feature reuses it unchanged. See Phase L below.

**2026-07-12 addition — User Story 8 & 9 (generalized metric display + admin enable/disable, FR-036–FR-042)**: The article card, detail dialog, and sort control still hardcode a single `citation_count` field end-to-end even though the metric catalog itself was already generalized in the original rework — this closes that gap so any catalog metric automatically appears in all three UI surfaces with zero further code changes, plus lets administrators toggle which metrics are active (a narrow, explicit amendment to FR-022 — see FR-041). Follows the existing `llm_providers` admin-catalog pattern (`backend/routers/llm_providers.py`, `frontend/app/admin/llm-providers/page.tsx`) for the new admin surface. See Phase M below.

**2026-07-14 addition — User Story 10 (weekly report chat-pin UX refinements, FR-043–FR-051)**: Phase L's report-level pin control turned out to dump one pill per cited article into `InlineQABarWrapper`, which doesn't scale past a couple of sources. Redesigns pinning as one editable "batch" pill per report (new frontend-only `PinnedGroup` state on `PinnedArticleProvider`), adds drag-and-drop from the widget's source pills into the chat input (`@dnd-kit/core`, already a dependency, used elsewhere via `useDraggable`/`useDroppable`), moves the pinned-pills row below the chat input, collapses the source pill list by default, and fixes an unrelated stepper bug where the date picker drifts once a topic has many weekly reports. Purely additive frontend work — no backend, migration, or RAG changes. See Phase O below.

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

**Re-check for 2026-07-12 citation addition**: ✅ All gates still pass. §I DDD — citation logic is entirely prompt/value-object/use-case changes inside the existing `intelligence` module; no new domain artifact type. §II Atomic Frontend — the new `CitedContent` component is extracted from existing `components/features/chat/AnswerDisplay.tsx` into the same `chat/` feature directory (not a new top-level feature), consumed by both `chat/` and `weekly-report/`; this is a reuse-first refactor, exactly what §II's "Reuse first" rule asks for. §III Test Discipline — new unit tests required for the prompt's citation instruction, the `article_ids` UUID fix, the translation citation-preservation fallback, and the `sources` resolution/skip-invalid-UUID logic; frontend unit test for the extracted `CitedContent` component. No new service, no new migration beyond what's already covered by `weekly_reports.article_ids` (column type unchanged — still `JSONB`, only the *values* stored change).

**Re-check for 2026-07-12 pin-into-chat addition (US7)**: ✅ All gates still pass. §I DDD — no `src/` changes at all; this is entirely a frontend wiring feature reusing an existing backend contract (`pinned_article_ids`) unchanged. §II Atomic Frontend — reuses the existing `usePinnedArticle` provider and `PinnedArticle` type rather than inventing a parallel pinning mechanism (reuse-first); the weekly report's pin control follows the same icon/toggle pattern as `article-card.tsx`'s existing Sparkles pin button. §III Test Discipline — unit tests required for the provider's new bulk pin/unpin helper, the widget's pin-control toggle state, and `InlineQABarWrapper`'s header forwarding. No new service, no new migration, no `chatbot-plugin` changes.

**Re-check for 2026-07-12 metric generalization addition (US8/US9)**: ✅ All gates still pass. §I DDD — no `src/` changes; `article_metric_values`/`metric_definitions` already live in the `collection`-adjacent shared schema from the original 014 migration, this only adds one column (`icon_name`) and generalizes existing backend query/schema code, no new bounded context. §II Atomic Frontend — new admin page (`frontend/app/admin/metric-definitions/page.tsx`) explicitly follows the existing `llm-providers` admin page's conventions (card list, `Switch` toggle, `require_admin`-gated, Storybook story required); `article-card.tsx`/`article-detail-dialog.tsx`/`sort-select.tsx` are extended, not replaced. §III Test Discipline — unit + integration tests required for the generalized sort logic, the new public/admin endpoints, the enabled-toggle permission boundary (non-admin denied), and the frontend badge-list rendering. §IX FastAPI Microservice Structure — new router follows existing `backend/routers/` + `backend/services/` split, mirroring `llm_providers.py`.

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
| Position-based `[N]` citations (LLM cites list position) instead of LLM-supplied article IDs | Avoids fabricated/hallucinated references — the LLM only ever sees a plain number, never an identifier it could get wrong; the use case is the sole source of truth mapping N → real UUID, matching the same pattern already proven in the chat feature | Asking the LLM to echo back an article ID or title per citation was considered — rejected because LLM output would need validation/repair logic for malformed or hallucinated IDs, adding failure modes with no benefit over position-based reference |
| Extracting `CitedContent` out of `AnswerDisplay.tsx` into a shared component rather than duplicating the parsing logic in `weekly-report-widget.tsx` | Two independent implementations of `[N]` parsing + citation-chip rendering would drift out of sync over time (e.g. one gets a bugfix, the other doesn't); §II's reuse-first rule applies directly | Copy-pasting `parseInline`/`renderMarkdown` into the weekly report widget was considered — rejected as the kind of duplication the constitution explicitly asks reviewers to avoid |
| Reusing the existing `usePinnedArticle` context + `X-Pinned-Article-Ids` header mechanism for US7 instead of a report-specific pinning path | The floating chatbot already proves this mechanism works end-to-end (frontend state → header → backend forwarding → filtered RAG retrieval); building a second pinning path for "report articles" specifically would duplicate all of that for no behavioral difference | A dedicated `pinned_report_id` concept (pin the whole report as one unit, resolved server-side) was considered — rejected because it would require a new backend contract and a new chatbot-plugin code path when the existing per-article-id mechanism already does exactly what's needed once fed the report's article ids |
| No forced re-ingestion / readiness check for unindexed cited articles before pinning (US7) | Pinning an unindexed article already degrades gracefully today (empty retrieval, no error); adding a synchronous "wait for ingestion" or "warn the user" step would add latency/complexity for a case that's already rare in practice (indexing happens earlier in the pipeline than weekly report generation) and not required by any acceptance scenario | A pre-flight check that calls the ingestion pipeline for any unindexed cited article before allowing pin was considered — rejected as scope creep beyond what US7's acceptance scenarios ask for; revisit only if real usage shows this matters |
| Narrow amendment to FR-022 (admin may toggle `enabled` only, not define metrics) instead of leaving it fully migration-only or fully opening the catalog to admin editing | The original FR-022 rejection was specifically about admins defining arbitrary extraction/field mappings — a real RCE/UX-cost concern (FR-023) that doesn't apply to flipping a boolean on an already-vetted entry; leaving `enabled` migration-only forces a deployment for a config change comparable in kind to toggling an `llm_providers.is_active` flag, which is already admin-dashboard-editable today | Two alternatives considered: (a) keep FR-022 fully migration-only, including `enabled` — rejected as an inconsistent double standard next to the existing `llm_providers` admin UI; (b) open the whole catalog row (incl. extraction config) to admin editing — rejected, reintroduces exactly the risk/UX-cost FR-022/FR-023 were written to avoid |
| `icon_name` stored on `metric_definitions` (duplicated across a metric_key's provider rows) rather than a new metric_key-level table | **Superseded same day (Phase N) — see the two rows below.** Follows the exact convention `label_i18n_key`/`format_hint`/`unit` already use on this same per-provider-row table — introducing a second table just for display fields would be a bigger schema change for a problem the codebase already accepted the tradeoff for | Splitting into a `metric_key`-level table (display fields) + a `metric_key + provider`-level table (extraction fields) was considered — rejected as disproportionate: it would require migrating three already-shipped columns, not just adding one, for a duplication risk that's already maintainer-review-mitigated in practice |
| `metric_definitions`/`metric_providers` split (Phase N, reverses the row above) | Once `icon_name`/`enabled` became admin-editable (not just `enabled`), the "duplication risk is maintainer-review-mitigated" argument stopped applying — an admin editing `icon_name` on one provider row would silently desync it from the metric_key's other provider rows, a bug the previous design invited. Splitting so `metric_definitions` is genuinely one row per metric_key removes the possibility of desync entirely, and lets the admin page/API stop exposing provider/priority at all | Keeping one table and just writing `icon_name`/`enabled` to every provider row on every admin edit was considered — rejected as accidental complexity (every write becomes a multi-row `UPDATE ... WHERE metric_key = ...`) papering over what should just be a foreign key |
| `metric_providers` stays a DB table rather than moving to a plain Python constant, even though it's never admin-edited | Discussed directly and kept as-is: a maintainer adding a metric_key sourced from an *already-registered* provider (its fetcher already exists in `build_provider_fetchers()`) can do it via a migration `INSERT` alone, no `.py` file to touch — narrower benefit than it first appears (a genuinely new external API always needs a new fetcher function regardless), but real for the common case | Moving `metric_providers` to a Python dict/list constant (mirroring `CODE_EXTRACTOR_REGISTRY`'s existing pattern in the same file) was proposed and left as a live option for a future simplification pass — not done now because the migration-only cost, for a single maintainer, was judged roughly a wash against the join/FK overhead of keeping it in DB; revisit if the extra table ever feels like more trouble than it's worth |
| Icon picker constrained to a fixed ~20-name whitelist rather than lucide-react's full icon catalog | Confirmed against lucide-react's own docs: its `DynamicIcon`/`dynamicIconImports` mechanism for load-by-name icon pickers is explicitly *not recommended* by the maintainers ("imports all icons during the build"); a small statically-imported whitelist has zero extra bundle cost since the icons are already imported, and matches the existing maintainer-curates-the-option-set governance already used for the rest of the catalog | `DynamicIcon` from `lucide-react/dynamic` was evaluated for a "browse all ~1500 icons" admin picker — rejected per lucide's own guidance, and because a handful of curated options each maintainer already imports when adding a metric is enough for actual recommendation-signal icons (citations, views, awards, etc.) |
| `semantic_scholar_arxiv` as a distinct `metric_providers` row rather than making the existing `semantic_scholar` fetcher accept either identifier | Keeps `priority` meaningful as an explicit, inspectable fallback order (DOI via OpenAlex → DOI via Semantic Scholar → arXiv ID via Semantic Scholar) rather than hiding a secondary lookup strategy inside one fetcher function; also mirrors that `openalex`'s fetcher deliberately has no arXiv equivalent (OpenAlex's API doesn't support it) — the catalog should reflect real per-provider capability, not paper over it | Making `build_provider_fetchers()["semantic_scholar"]` internally try DOI-then-arXiv in one callable was considered — rejected because it would silently conflate two different lookup strategies under one `priority` value, losing the ability to reason about (or independently disable) either |

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
│   ├── articles.py         # extend: citation_count/view_count in ArticleOut, POST /articles/{id}/view, sort by new fields; 2026-07-12: sort generalized to any enabled metric_key (US8)
│   ├── weekly_reports.py   # new: GET /weekly-reports, GET /weekly-reports/latest; 2026-07-12: _to_out() resolves `sources` from article_ids
│   ├── metric_definitions.py  # 2026-07-12 new (US8/US9): GET /metric-definitions (public, enabled+deduped display metadata), GET /admin/metric-definitions (admin, all rows), PATCH /admin/metric-definitions/{id} (admin, enabled only)
│   └── user.py             # new: GET|PUT /user/notification-settings, GET|POST|DELETE /user/subscriptions/{topic_id}
├── schemas/
│   ├── article.py          # extend ArticleOut + ArticleDetailOut with citation_count, view_count; 2026-07-12: citation_count → metrics: Dict[str, float] (US8)
│   ├── weekly_report.py    # new: WeeklyReportOut; 2026-07-12: + ArticleSourceOut, WeeklyReportOut.sources
│   └── metric_definition.py  # 2026-07-12 new (US8/US9): MetricDefinitionDisplayOut (public); Phase N same day: MetricDefinitionAdminOut drops provider_name/priority, MetricDefinitionAdminUpdate (enabled + icon_name, ICON_WHITELIST-validated) replaces MetricDefinitionEnabledUpdate
└── services/
    ├── article_service.py  # extend: JOIN article_metrics (view_count) + article_metric_values (citation_count, filtered metric_key='citation_count') for sort + output; view count flush logic unchanged; 2026-07-12: build_article_out() emits generic metrics map, get_articles_paginated() sort generalized (US8)
    ├── weekly_report_service.py  # new: get_weekly_reports, get_latest_weekly_report
    └── metric_definition_service.py  # 2026-07-12 new (US8/US9): get_enabled_metric_display, get_all_metric_definitions; Phase N same day: update_metric_definition(enabled, icon_name) replaces set_metric_definition_enabled

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
│       │       ├── article_summary_for_report.py  # new: per-article prompt input DTO; 2026-07-12: + article_id field
│       │       ├── weekly_report_prompt.py        # new: extends BasePrompt; 2026-07-12: numbered article list + [N] citation instruction
│       │       └── image_generation_prompt.py     # new: extends BasePrompt
│       │       # WeeklyReportTranslationPrompt lives in translation_prompt.py (alongside ArticleTranslationPrompt etc., pre-existing file) — 2026-07-12: + instruction to preserve [N] markers verbatim
│       └── application/
│           └── use_cases/
│               └── generate_weekly_report.py      # new; 2026-07-12: fix article_ids bug (was titles, now real UUIDs, citation-order-aligned); _translate_report() validates translated [N] markers match original, falls back to English summary_text on mismatch
├── infrastructure/
│   ├── collection/
│   │   ├── scrapers/
│   │   │   ├── openalex_scraper.py     # extend: populate metric_seeds={"citation_count": ...} on ScrapedArticle
│   │   │   └── semantic_scholar_scraper.py  # extend: same, metric_seeds
│   │   ├── clients/
│   │   │   ├── openalex_client.py           # new method: fetch_by_doi(doi) -> Optional[dict] (raw JSON, for refresh job)
│   │   │   └── semantic_scholar_client.py    # new method: fetch_by_doi(doi) -> Optional[dict]; Phase N same day: + fetch_by_arxiv_id(arxiv_id) -> Optional[dict]
│   │   └── metrics/                          # new subpackage
│   │       ├── json_path_extractor.py        # new: JsonPathMetricExtractor (jmespath-based, generic)
│   │       └── resilient_metrics_service.py  # new: ResilientMetricsService (mirrors ResilientLLMService); Phase N same day: build_provider_fetchers() + "semantic_scholar_arxiv" entry
│   ├── persistence/
│   │   └── collection/
│   │       └── article_metrics_repo_impl.py  # revise: upsert() writes N rows to article_metric_values instead of 1 column
│   ├── intelligence/
│   │   ├── image/
│   │   │   ├── base_image_provider.py         # new
│   │   │   └── gemini_imagen_provider.py      # new
│   │   └── repositories/
│   │       └── weekly_report_repo_impl.py     # new; 2026-07-12: fetch_top_articles() additionally SELECTs Article.id → ArticleSummaryForReport.article_id
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
├── metric_definition.py        # new; 2026-07-12: + icon_name column (US8/US9); Phase N same day: rewritten to metric-key-only shape (provider_name/priority/extractor_type/extractor_spec moved out)
├── metric_provider.py          # Phase N new (2026-07-12, same day): provider_name, priority, extractor_type, extractor_spec, FK metric_definition_id
├── article_metric_value.py     # new
├── weekly_report.py            # new
└── user_subscription.py        # new: UserTopicSubscription + UserNotificationSettings + UserArticleFavorite

# Alembic migrations
alembic/versions/
└── 23_article_recommendation_weekly_report.py  # all new tables (incl. metric_definitions + article_metric_values + seed data + articles.metadata expression indexes) + llm_provider type column; 2026-07-12 (US8/US9): edited in place to add metric_definitions.icon_name + seed values; Phase N same day: edited in place again — metric_definitions split into metric_definitions (metric-key-level) + new metric_providers table, seed restructured with 3 providers incl. semantic_scholar_arxiv — still no follow-up revision, still unshipped

# Frontend
frontend/
├── app/
│   ├── page.tsx                    # extend: add WeeklyReportWidget above InlineQABarWrapper
│   └── admin/
│       └── metric-definitions/
│           └── page.tsx            # 2026-07-12 new (US9): list all metric_definitions rows grouped by metric_key, enabled Switch toggle per row, require_admin-gated — mirrors admin/llm-providers/page.tsx's card-list + Switch conventions (read-only otherwise, no create/edit/delete/reorder)
├── components/
│   └── features/
│       ├── articles/
│       │   ├── article-card.tsx             # extend: heart icon (left of title), citation_count badge, view_count, fire view event; 2026-07-12: citation-only badge → generic loop over article.metrics using fetched display metadata, default icon fallback (US8)
│       │   ├── article-detail-dialog.tsx    # extend: citation_count + view_count display; 2026-07-12: same generalization as article-card.tsx (US8)
│       │   ├── sort-select.tsx              # 2026-07-12: SORT_OPTIONS fixed fields unchanged; dynamically appends one option per enabled catalog metric fetched from GET /metric-definitions (US8)
│       │   └── filter-bar.tsx               # extend: sort dropdown on right + Favorites toggle
│       ├── chat/
│       │   ├── cited-content.tsx            # 2026-07-12 new: <CitedContent text sources /> extracted from AnswerDisplay.tsx (parseInline, renderMarkdown, source-chip list, ArticleDetailDialog-open-on-click)
│       │   ├── AnswerDisplay.tsx             # 2026-07-12: refactored to render via CitedContent instead of inline logic
│       │   └── InlineQABarWrapper.tsx        # 2026-07-12 (US7): + usePinnedArticle() wiring, X-Pinned-Article-Ids header, pinned-chip row (mirrors FloatingChatbotWrapper.tsx's existing pattern)
│       └── weekly-report/                   # new feature directory
│           ├── weekly-report-widget.tsx     # 2026-07-12: render selected.summary_text via <CitedContent text sources={selected.sources} /> instead of manual splitParagraphs; + report-level pin control (US7)
│           ├── weekly-report-skeleton.tsx
│           └── weekly-report-widget.stories.tsx  # required by Constitution §II
└── lib/
    ├── providers/
    │   └── pinned-article-provider.tsx      # 2026-07-12 (US7): + bulk pin/unpin helper for "pin all of this report's articles"
    └── api/
        ├── articles.ts             # extend: recordArticleView(), update types (citation_count, view_count, is_favorited); 2026-07-12: citation_count → metrics: Record<string, number> (US8)
        ├── weekly-reports.ts       # new; 2026-07-12: WeeklyReport type + sources: ArticleSource[]
        ├── metric-definitions.ts   # 2026-07-12 new (US8/US9): fetchEnabledMetricDefinitions() (public), fetchAllMetricDefinitions()/updateMetricDefinitionEnabled() (admin)
        └── user.ts                 # new or extend: subscriptions, notification settings, favorites (addFavorite, removeFavorite, getFavorites)
```

`frontend/app/settings/layout.tsx`'s admin tab list (2026-07-12, US9): add a `/admin/metric-definitions → admin.metricDefinitions` entry alongside the existing five tabs.

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

### Phase K: Weekly Report Citations (2026-07-12, User Story 6, FR-024–FR-029)

**Goal**: Weekly report summaries carry `[N]` inline citations resolvable to real articles; fixes the `article_ids` title-string bug as a prerequisite.

1. Fix `ArticleSummaryForReport` (`src/modules/intelligence/domain/value_objects/article_summary_for_report.py`): add `article_id: UUID` field
2. Fix `WeeklyReportRepoImpl.fetch_top_articles()` (`src/infrastructure/persistence/intelligence/weekly_report_repo_impl.py`): additionally `SELECT Article.id`, populate `article_id` on each `ArticleSummaryForReport`
3. Update `WeeklyReportPrompt.render()` (`src/modules/intelligence/domain/value_objects/weekly_report_prompt.py`): render articles as a 1-indexed bracketed list; add instruction to cite inline via `[N]` in `summary_text`, where `N` is list position (not an LLM-supplied ID)
4. Fix `GenerateWeeklyReportUseCase` (`src/modules/intelligence/application/use_cases/generate_weekly_report.py`, ~line 132): `article_ids = [str(a.title) for a in articles]` → `[str(a.article_id) for a in articles]`, order preserved
5. Update `WeeklyReportTranslationPrompt` (`src/modules/intelligence/domain/value_objects/translation_prompt.py` — lives alongside the other translation prompt value objects, not a standalone file): add instruction to preserve `[N]` markers verbatim during translation
6. Update `GenerateWeeklyReportUseCase._translate_report()` (there is no standalone `TranslateWeeklyReportUseCase` — translation is a private method on the same use case): after translating `summary_text`, compare the set of `[N]` tokens against the original; on mismatch, store the original English `summary_text` for that language's row instead of the translated one
7. Add `ArticleSourceOut` schema and `sources: List[ArticleSourceOut] = []` field to `WeeklyReportOut` (`backend/schemas/weekly_report.py`)
8. Update `_to_out()` (`backend/routers/weekly_reports.py`): resolve `sources` by looking up `Article` rows for `report.article_ids` in order; wrap each entry's `UUID(...)` parse in try/except, skipping unparseable (pre-existing title-string) entries so old reports resolve to an empty `sources` list
9. Extract `CitedContent` component (`frontend/components/features/chat/cited-content.tsx`) from `AnswerDisplay.tsx`'s `parseInline`/`renderMarkdown`/source-chip-list/`ArticleDetailDialog`-open logic; refactor `AnswerDisplay.tsx` to use it
10. Add `sources: ArticleSource[]` to the `WeeklyReport` type (`frontend/lib/api/weekly-reports.ts`)
11. Update `weekly-report-widget.tsx` to render `selected.summary_text` via `<CitedContent text={selected.summary_text} sources={selected.sources} />` instead of the manual `splitParagraphs(...).map(p => <p>)` block

### Tests (Phase K)
1. Unit test: `WeeklyReportPrompt.render()` produces a numbered article list and the citation instruction
2. Unit test: `GenerateWeeklyReportUseCase` populates `article_ids` with real UUIDs in prompt order (regression test for the title-string bug)
3. Unit test: `TranslateWeeklyReportUseCase` falls back to the English `summary_text` when translated `[N]` markers don't match the original
4. Backend integration test: `GET /weekly-reports/latest` (or equivalent) resolves `sources` correctly for a report with valid UUID `article_ids`, and returns an empty `sources` list (no error) for a report with pre-existing title-string `article_ids`
5. Frontend unit test: `CitedContent` renders `[N]` as a clickable marker only when `N` is within `sources` range, and renders out-of-range/malformed markers as literal text
6. Frontend unit test: `AnswerDisplay` still renders identically after the `CitedContent` extraction (no behavior regression in chat)

### Phase L: Pin Weekly Report into Chat (2026-07-12, User Story 7, FR-030–FR-034)

**Goal**: A report-level pin control on the weekly report widget bulk-adds the report's cited articles into the shared pinned-article chat context; the homepage's inline chat bar gains the pinning wiring it currently lacks. No backend changes — reuses the existing `pinned_article_ids` → filtered-retrieval mechanism unchanged.

1. Extend `PinnedArticleContextValue` (`frontend/lib/providers/pinned-article-provider.tsx`) with `pinArticles(articles: PinnedArticle[])` (adds any not already present) and `areAllPinned(ids: string[])` (helper for the widget's toggle state); keep existing per-article API (`togglePinnedArticle`, `removePinnedArticle`, `clearPinnedArticles`, `isPinned`) unchanged
2. Add a report-level pin control to `frontend/components/features/weekly-report/weekly-report-widget.tsx`: a Sparkles-style button (mirrors `article-card.tsx`'s existing per-article pin button) shown only when `selected.sources.length > 0`; toggling calls `pinArticles(selected.sources.map(...))` when not fully pinned, or removes each of `selected.sources`' ids when fully pinned
3. Wire `usePinnedArticle()` into `frontend/components/features/chat/InlineQABarWrapper.tsx`: build the `X-Pinned-Article-Ids` header from `pinnedArticles` exactly as `FloatingChatbotWrapper.tsx` already does; render a compact pinned-chip row above the `AgentInput` showing each pinned article's title with a per-chip remove action

### Tests (Phase L)

1. Unit test: `pinArticles()` adds only the articles not already present (no duplicates); `areAllPinned()` returns true only when every given id is present
2. Frontend unit test: the weekly report widget's pin control is hidden when `sources` is empty, pins all cited articles when none/some are pinned, and unpins all of them when all are already pinned
3. Frontend unit test: `InlineQABarWrapper` includes `X-Pinned-Article-Ids` in the chat request headers when articles are pinned, and omits it when none are pinned

### Phase M: Generalized Metric Display + Admin Enable/Disable (2026-07-12, User Story 8 & 9, FR-036–FR-042)

**Superseded same day by Phase N below** — steps 1, 3–5, 8, 13 here describe a single `metric_definitions` table (`provider_name`/`priority` alongside display config, only `enabled` admin-editable) that was replaced before Phase M finished being reviewed. Kept for history; see Phase N for what actually shipped.

**Goal**: Any catalog metric (not just `citation_count`) automatically appears as a badge on article cards/detail dialog and as a sort option, driven by a new public display-metadata endpoint; administrators can toggle a metric's enabled state from a new admin page, without touching its extraction or display configuration.

1. **Edit migration `23_article_recommendation_weekly_report.py` in place** (still unshipped to production as of 2026-07-12 — same rationale as the earlier citation_count/metric_definitions rework, do not add a follow-up revision): add nullable `icon_name VARCHAR(50)` column to the `metric_definitions` `create_table()`; add `icon_name` to the seed `INSERT` for the existing `citation_count` rows (openalex/semantic_scholar, e.g. `'quote'`)
2. Add `icon_name = Column(String(50), nullable=True)` to `models/metric_definition.py`
3. Create `backend/schemas/metric_definition.py`: `MetricDefinitionDisplayOut` (`metric_key`, `label_i18n_key`, `icon_name`, `format_hint`, `unit` — public shape, no provider/extraction fields), `MetricDefinitionAdminOut` (adds `id`, `provider_name`, `priority`, `enabled`), `MetricDefinitionEnabledUpdate` (`enabled: bool` — the only admin-editable field)
4. Create `backend/services/metric_definition_service.py`: `get_enabled_metric_display(db)` (query `enabled=True`, dedupe by `metric_key` ordered by `priority`, return `MetricDefinitionDisplayOut` list), `get_all_metric_definitions(db)` (all rows, for the admin page), `set_metric_definition_enabled(db, id, enabled)` (updates one row by id, `enabled` only — no other field accepted)
5. Create `backend/routers/metric_definitions.py`: `GET /metric-definitions` (public, calls `get_enabled_metric_display`), `GET /admin/metric-definitions` (`require_admin`, calls `get_all_metric_definitions`), `PATCH /admin/metric-definitions/{id}` (`require_admin`, calls `set_metric_definition_enabled`); register in `backend/main.py`
6. Edit `backend/schemas/article.py`: replace `citation_count: Optional[int] = None` on `ArticleOut`/`ArticleDetailOut` with `metrics: Dict[str, float] = {}`
7. Edit `backend/services/article_service.py::build_article_out()` and `get_articles_paginated()`: fetch every non-NULL `article_metric_values` row for the page's article ids (same two-query pattern as `WeeklyReportRepoImpl.fetch_top_articles()` from Phase K) and populate `ArticleOut.metrics`; generalize the `if sort in ("citation_count", "view_count")` branch so any `sort` value matching an enabled `metric_definitions.metric_key` uses the same outerjoin+nullslast ordering pattern, keyed by that `sort` value instead of a hardcoded string
8. Create `frontend/lib/api/metric-definitions.ts`: `fetchEnabledMetricDefinitions()` (public), `fetchAllMetricDefinitions()` / `updateMetricDefinitionEnabled(id, enabled)` (admin, under `/api/proxy/admin/metric-definitions`)
9. Update `frontend/lib/api/articles.ts`'s `Article`/`ArticleDetail` types: `citation_count?: number | null` → `metrics: Record<string, number>`
10. Create a small icon lookup, e.g. `frontend/components/features/articles/metric-icons.ts` exporting `Record<string, LucideIcon>` (whitelisted names only) + a default fallback icon (e.g. `BarChart3`)
11. Edit `article-card.tsx` and `article-detail-dialog.tsx`: replace the hardcoded `citation_count > 0 && <Quote>` badge with a loop over `Object.entries(article.metrics)`, resolving each `metric_key`'s icon/label via a fetched `fetchEnabledMetricDefinitions()` list (cached at a level shared by all cards on the page, e.g. a small hook or the existing articles page-level fetch, not one fetch per card)
12. Edit `sort-select.tsx`: fetch `fetchEnabledMetricDefinitions()` once, append one `SORT_OPTIONS` entry per returned metric (`value: metric_key`, `labelKey: label_i18n_key`) after the fixed fields
13. Create `frontend/app/admin/metric-definitions/page.tsx`: fetch `fetchAllMetricDefinitions()`, render one card per row grouped by `metric_key` (mirroring `admin/llm-providers/page.tsx`'s `AccordionSection` + card pattern), each with a `Switch` bound to `enabled` calling `updateMetricDefinitionEnabled()` optimistically with rollback on failure — no create/edit/delete/reorder controls
14. Add the new tab to `frontend/app/settings/layout.tsx`'s admin nav list; add `admin.metricDefinitions` (and any other new labels) to `en.json`/`zh-TW.json`

### Tests (Phase M)

1. Backend unit/integration test: `GET /metric-definitions` returns only `enabled=true` rows, deduplicated by `metric_key`, without `provider_name`/`extractor_spec` in the response
2. Backend integration test: `GET /admin/metric-definitions` and `PATCH /admin/metric-definitions/{id}` both return 401/403 for a non-admin caller (FR-042's access boundary, US9 acceptance scenario 4)
3. Backend integration test: `PATCH /admin/metric-definitions/{id}` updates only `enabled`; a request body containing other fields (e.g. `extractor_spec`) either is ignored or rejected, never applied
4. Backend integration test: `GET /articles` returns a `metrics` map with entries for every catalog metric the article has a value for (not just citation_count), and sorting by an enabled metric_key orders correctly with nulls-last regardless of direction
5. Frontend unit test: `article-card.tsx` renders one badge per `metrics` entry with the correct icon/label from a mocked `fetchEnabledMetricDefinitions()`, and falls back to the default icon when a metric's `icon_name` is null
6. Frontend unit test: `sort-select.tsx` includes a dynamically-fetched metric option alongside the fixed fields
7. Frontend unit test: `admin/metric-definitions/page.tsx` toggles a `Switch`, calls `updateMetricDefinitionEnabled()`, and rolls back the UI state if the call fails

### Phase N: Metric/Provider Table Split + arXiv Citation Coverage (2026-07-12, same day, supersedes Phase M's steps 1/3–5/8/13)

**Why**: Two issues surfaced discussing Phase M before it was considered done. (1) The admin page ended up showing `provider_name`/`priority` per row because `metric_definitions` conflated admin-facing display config with maintainer-only extraction config in one `(metric_key, provider_name)`-keyed table — admins should only ever see/edit one row per metric_key (enabled + icon), never provider/priority. (2) `refresh_metrics.py`'s two provider fetchers (`openalex`, `semantic_scholar`) both only ever used `ids["doi"]`, silently ignoring `ids["arxiv_id"]` even though the stale-articles query and `articles.metadata` expression indexes already support arXiv-only articles — meaning arXiv preprints with no DOI got zero citation refresh. Root-caused during discussion: `article.source` (how an article was scraped) is unrelated to which external database can supply its citation count — that's determined by which identifiers (DOI/arXiv ID) the article carries, not by scrape provenance; a same-underlying-paper-scraped-from-multiple-sources dedup gap was also identified but is out of scope here (tracked separately).

**Goal**: Admin page shows one row per metric_key with zero extraction-plumbing leakage; arXiv-only articles can get `citation_count` refreshed via Semantic Scholar (the only one of the two providers whose API accepts an arXiv ID).

1. **Edit migration `23_article_recommendation_weekly_report.py` in place again** (still unshipped): `metric_definitions` becomes metric_key-level only — drop `provider_name`/`priority`/`extractor_type`/`extractor_spec`, keep `metric_key` (now `UNIQUE` by itself), `label_i18n_key`, `format_hint`, `unit`, `icon_name`, `enabled`. New `metric_providers` table: `metric_definition_id` (FK → `metric_definitions.id`, `ON DELETE CASCADE`), `provider_name`, `priority`, `extractor_type`, `extractor_spec`; `UNIQUE(metric_definition_id, provider_name)`. Seed: one `metric_definitions` row for `citation_count`, three `metric_providers` rows — `openalex` (priority 1, DOI), `semantic_scholar` (priority 2, DOI), `semantic_scholar_arxiv` (priority 3, arXiv ID — new). `downgrade()` drops `metric_providers` before `metric_definitions` (FK). Local Postgres brought in sync via a hand-run equivalent `DROP TABLE`/`CREATE TABLE`/re-seed (not a full alembic downgrade/upgrade, to avoid touching unrelated local data) — same in-place-edit rationale as every other touch of migration 23 this feature.
2. Rewrite `models/metric_definition.py` to the new metric-key-only shape; add `models/metric_provider.py` (new); register both in `models/__init__.py`
3. Rewrite `shared/metric_definition.py::load_enabled_metric_definitions()` to `JOIN metric_definitions` (filtered `enabled=True`) with `metric_providers`, still returning the same flat `{metric_key, provider_name, priority, extractor_type, extractor_spec}` dict shape — `resilient_metrics_service.py` needs zero changes as a result
4. Add `SemanticScholarClient.fetch_by_arxiv_id(arxiv_id)` (`src/infrastructure/collection/clients/semantic_scholar_client.py`) — same shape as `fetch_by_doi()`, hits `paper/ARXIV:<id>` (confirmed against Semantic Scholar's public API docs); add a `"semantic_scholar_arxiv"` entry to `build_provider_fetchers()` (`resilient_metrics_service.py`) calling it only when `ids.get("arxiv_id")`. OpenAlex gets no equivalent — confirmed against OpenAlex's docs that single-item lookup only accepts DOI/PMID/PMCID/MAG ID, no arXiv ID
5. Rewrite `backend/schemas/metric_definition.py`: `MetricDefinitionDisplayOut` unchanged (public shape was already metric-key-level); `MetricDefinitionAdminOut` drops `provider_name`/`priority`; `MetricDefinitionAdminUpdate` (renamed from `MetricDefinitionEnabledUpdate`) accepts `enabled: Optional[bool]` AND `icon_name: Optional[str]`, the latter validated by a Pydantic `field_validator` against `ICON_WHITELIST` (module-level constant, kept in sync with the frontend whitelist — see step 8)
6. Rewrite `backend/services/metric_definition_service.py`: `get_all_metric_definitions()` now a plain `metric_definitions` query (no join needed for the admin list); `update_metric_definition(db, id, *, enabled, icon_name)` (renamed from `set_metric_definition_enabled`) sets whichever of the two fields is provided
7. Update `backend/routers/metric_definitions.py`: `PATCH /admin/metric-definitions/{id}` now uses `MetricDefinitionAdminUpdate`/`update_metric_definition`
8. Expand `frontend/components/features/articles/metric-icons.ts`'s whitelist from 8 to 20 icons (add `download`, `share-2`, `bookmark`, `heart`, `message-square`, `flame`, `trophy`, `hash`, `percent`, `clock`, `book-open`, `network` — broader coverage of plausible future article/recommendation metrics); export `METRIC_ICON_NAMES: string[]` for the admin icon picker
9. Update `frontend/lib/api/metric-definitions.ts`: `MetricDefinitionAdmin` drops `provider_name`/`priority`; `updateMetricDefinitionEnabled(id, enabled)` replaced by `updateMetricDefinition(id, {enabled?, icon_name?})`
10. Rewrite `frontend/app/admin/metric-definitions/page.tsx`: one row per metric_key (not per provider) — `Switch` for `enabled` + a `NativeSelect` (`@/components/ui/native-select`, not a full lucide "complete catalog" dynamic-icon picker — deliberately rejected, see Complexity Tracking) populated from `METRIC_ICON_NAMES` for `icon_name`; both call `updateMetricDefinition()` optimistically with rollback on failure
11. Update `CLAUDE.md`: correct the "LLM Provider Chain" section (`providers.toml` does not exist in this repo — confirmed by search; provider config has been DB-driven via the `llm_providers` table since migration 16, `shared/llm_provider.py::load_active_providers()` et al.); add a new "Metric Provider Chain" section documenting the `metric_definitions`/`metric_providers` split and contrasting it with the LLM chain (interchangeable providers + rate-limit fallback vs. non-interchangeable providers + identifier/coverage-driven fallback); add `MetricDefinition`/`MetricProvider` to the ORM Models bullet list; add `llm_providers.py`, `metric_definitions.py`, `weekly_reports.py` rows to the Backend Routers table (pre-existing gaps noticed in passing, not a full audit)

### Tests (Phase N)

1. Backend integration test: `GET /metric-definitions` public shape unchanged (still metric-key-level, no provider/priority — this was already true, verify it stays true post-split)
2. Backend integration test: `GET /admin/metric-definitions` returns exactly one row per metric_key even when it has multiple `metric_providers` rows, and that row exposes neither `provider_name` nor `priority`
3. Backend integration test: `PATCH /admin/metric-definitions/{id}` accepts `icon_name` from the whitelist and persists it; rejects (422) an `icon_name` outside the whitelist; a body with only `enabled` leaves `icon_name` untouched and vice versa
4. Backend unit test: `SemanticScholarClient.fetch_by_arxiv_id()` hits `paper/ARXIV:<id>`, returns the raw JSON, raises `SemanticScholarRateLimitedError` on 429, returns `None` on other failures
5. Backend unit test: `build_provider_fetchers()["semantic_scholar_arxiv"]` calls `fetch_by_arxiv_id()` only when `arxiv_id` is present, never when only `doi` is given; `build_provider_fetchers()["openalex"]` is never called with only an `arxiv_id` (regression guard — this was the original bug)
6. Frontend unit test: admin page renders one card per metric_key with no provider/priority text visible anywhere, even when the underlying fixture has multiple providers for the same metric_key
7. Frontend unit test: changing the icon `NativeSelect` calls `updateMetricDefinition(id, { icon_name })`; toggling the `Switch` calls it with `{ enabled }`; both roll back on failure

### Phase O: Weekly Report Chat-Pin UX — Group Pills, Drag & Drop, Collapsible Sources, Stepper Fix (2026-07-14, User Story 10, FR-043–FR-051)

**Why**: Phase L's report-level pin control adds one pill per cited article to the chat input — fine for a handful of sources, but it floods `InlineQABarWrapper` once a report cites more than a couple of articles. Separately, the widget's source-citation pill row (Phase K) always renders every source at once, and the stepper's date picker (Phase H) has no scroll bound on its week-dots list, so it drifts or gets clipped once a topic accumulates many weekly reports. All four fixes touch the same widget family and were scoped together. Full design rationale in `docs/superpowers/specs/2026-07-14-weekly-report-chat-pinning-design.md`.

**Goal**: One compact, editable "batch" pill per weekly report replaces one-pill-per-article; source pills support drag-and-drop into chat; the pinned-pills row moves below the chat input; the source pill list is collapsed by default; the stepper's date picker stays fixed with jump-to-top/bottom controls when the week list overflows.

1. Extend `PinnedArticleContextValue` (`frontend/lib/providers/pinned-article-provider.tsx`) with a parallel `pinnedGroups: PinnedGroup[]` state (`{ id, dateLabel, articles }`, id = weekly report id) and three new actions: `pinGroup(group)` (upserts the group by id, pins every one of its articles via the existing additive `pinArticles`), `toggleGroupArticle(groupId, articleId)` (flips one article via the existing `togglePinnedArticle`; auto-removes the group from `pinnedGroups` once its included count hits 0), `removeGroup(groupId)` (unpins every article in the group and deletes it). Existing per-article API unchanged.
2. Edit `weekly-report-widget.tsx`'s `handleTogglePinReport`: same `areAllPinned(ids)` branch as today, but call `pinGroup({ id: selected.id, dateLabel, articles })` / `removeGroup(selected.id)` instead of the raw `pinArticles`/loop; `dateLabel` reuses the stepper's `{ month: 'short', day: 'numeric' }` format (step 7) for visual consistency
3. Add an opt-in `draggableSources?: boolean` prop (default `false`) to `frontend/components/features/chat/cited-content.tsx`; when true, wrap each source-chip button with dnd-kit's `useDraggable({ id: 'source-' + src.id, data: { article: { id, title } } })`. Chat's existing usage (outside any `DndContext`) is unaffected by the default
4. Add local state `sourcesExpanded` to `weekly-report-widget.tsx` (reset to `false` on every `selected.id` change); turn the existing `extraContent` article-count paragraph into a disclosure button (▸/▾) toggling it; pass `showSourceList={sourcesExpanded}` and `draggableSources` to `CitedContent`
5. Wrap `weekly-report-widget.tsx`'s returned JSX in dnd-kit's `<DndContext onDragEnd={handleDragEnd}>` (it's already the common ancestor of the draggable source pills and `{children}` = `InlineQABarWrapper`); `handleDragEnd` checks `event.over?.id === 'chat-input-dropzone'` and, if so, calls `pinArticles([event.active.data.current.article])` (additive single-pin, no-op if already pinned)
6. Edit `InlineQABarWrapper.tsx`: move the pinned-pills block from above `<AgentInput>` to below it; render one pill per `pinnedGroups` entry (`🌟 {dateLabel} · {includedCount} 篇文章` with edit + remove icons) before any individually-pinned articles not covered by a group (existing rendering, unchanged); edit icon opens a shadcn `Popover` (`components/ui/popover.tsx`) with a checkbox per `group.articles` entry bound to `isPinned(article.id)`, calling `toggleGroupArticle`; remove icon calls `removeGroup`; wrap the pinned-pills+input container with `useDroppable({ id: 'chat-input-dropzone' })`, highlighting it while `isOver`
7. Edit `weekly-report-stepper.tsx`: replace the separate `flex-1` spacer div with `overflow-y-auto flex-1 min-h-0` directly on the week-dots `listbox` div (with a `ref`), so it scrolls internally instead of pushing/clipping the date picker, which now stays pinned at the bottom of the column via normal flex-column order (no spacer needed). Track overflow via `ResizeObserver` (re-checked on `reports.length` change); when `scrollHeight > clientHeight`, render `ChevronUp`/`ChevronDown` buttons above/below the listbox that `scrollTo({ top: 0 | scrollHeight, behavior: 'smooth' })`; hidden when the list fits
8. Add new i18n keys under `rag.*` in `frontend/lib/providers/locales/en.json`/`zh-TW.json`: `weeklyGroupPill` (`"{date} · {count} articles"` / `"{date}·{count}篇文章"`), `editGroupArticles`, `groupArticlesPopoverTitle`; reuse the existing `rag.removeArticleRef` key for the batch pill's remove-icon aria-label

### Tests (Phase O)

1. Unit tests for `pinGroup`/`toggleGroupArticle` (including the auto-remove-at-zero-included behavior)/`removeGroup` in `frontend/tests/unit/pinned-article-provider.test.tsx`
2. `InlineQABarWrapper` unit test: renders a group pill with the correct live count; the edit popover's checkboxes reflect `isPinned`; a simulated drop event on the dropzone pins the dragged article
3. `weekly-report-widget.tsx` unit test: sparkles toggle still drives `areAllPinned` correctly through the new group actions; source pill list starts collapsed and expands on click; resets to collapsed when `selected.id` changes
4. `weekly-report-stepper.tsx` unit test: jump-to-top/bottom chevrons absent when the list fits, present and functional (scroll-to-top/bottom) when it overflows
5. `cited-content.tsx` unit test: existing citation tests unaffected by the new `draggableSources` prop (defaults `false`); a new test confirms drag attributes are present only when the prop is set

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
