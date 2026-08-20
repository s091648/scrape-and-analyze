# Contract: Async Repository Ports

**Files**: New Protocols in `src/modules/*/domain/repositories/` (one per repository listed below), new implementations in `src/infrastructure/persistence/{shared,collection,intelligence}/*_async_repo_impl.py`.
**Relationship to existing sync repositories**: Additive, not a replacement. See plan.md's Complexity Tracking and research.md item 3 for why these are separate classes rather than converting the existing sync ones in place.

## Repositories requiring a new async Protocol + adapter

| Domain repository | Used by (downstream, now-concurrent) | Existing sync class (untouched) |
|---|---|---|
| `ArticleRepository` | `ProcessScrapedArticleUseCase` (save only — `find_analyzed_url_hashes` stays sync, called only from the still-batched fetch/dedup phase) | `SqlAlchemyArticleRepository` |
| `AnalysisRepository` | `AnalyzeArticleUseCase` | `SqlAlchemyAnalysisRepository` |
| `AnalysesTranslationRepository` | `TranslateArticleUseCase` | `SqlAlchemyAnalysesTranslationRepository` |
| `TagTranslationRepository` | `TranslateTagsUseCase` | `SqlAlchemyTagTranslationRepository` |
| `ArticleTranslationRepository` | `TranslateArticleBodyUseCase` | `SqlAlchemyArticleTranslationRepository` |
| `TagRepository` | `NormalizeTagsUseCase` | `SqlAlchemyTagRepository` |
| `TagGroupDefinitionRepository` | `AnalyzeArticleUseCase` | `SqlAlchemyTagGroupDefinitionRepository` |
| `TopicRepository` | `AnalyzeArticleUseCase` — **confirmed shared with `build_weekly_pipeline()`** (`bootstrap.py:232`/`:534`), the concrete evidence for this whole contract's existence | `SqlAlchemyTopicRepository` |
| `FailedTaskRepository` | `FailedTaskPersistenceHandler` | `SqlAlchemyFailedTaskRepository` |

A full audit of whether any of the remaining repositories (`ArticleDedupRepository`, `ArticleMetricsRepository`, `ScraperSettingRepository`, `SearchTermRepository`, `RagBackfillRepository`, `WeeklyReportTranslationRepository`) also end up needing an async counterpart is a `/speckit-tasks`-time activity — none of them are used inside the per-article downstream chain today (`ArticleMetricsRepository`/`ScraperSettingRepository` are used only in the still-sync upstream phase; `SearchTermRepository` is used by the search-index rebuild, which runs once at Barrier 1, not per-article, and can stay sync; the rest belong to out-of-scope pipelines).

## Behavioral guarantees

- **Method-for-method parity with the existing sync Protocol it mirrors**: an async repository's methods MUST accept and return the same domain types (entities/value objects, unchanged `@dataclass`es — constitution Principle I) as its sync counterpart, differing only in being `async def` / requiring `await`. No new fields, no new validation rules, no behavior change beyond the calling convention — this is a mechanical port, not a redesign.
- **Session ownership**: each async repository instance is constructed with (and holds a reference to) exactly one `AsyncSession`, supplied by its caller (data-model.md's `Article Processing Unit of Work` — one session per task). An async repository instance MUST NOT be constructed once and reused across multiple concurrently-running tasks, and MUST NOT hold a sync `Session` under any circumstance.
- **No cross-talk with the sync engine**: async repositories use the `asyncpg`-backed `async_sessionmaker` (research.md item 2), a separate engine/connection pool from the existing sync `psycopg2`-backed one `database.py::get_session()` returns. Both point at the same PostgreSQL database; they are two independent connection pools to it, not two databases.
- **Errors surface as exceptions, not sentinel values** — matches the existing sync repositories' convention (domain exceptions subclassing `DomainError`, per CLAUDE.md's Exception Handling convention); an async repository method that fails raises, it does not return `None`/`False` to signal failure. This is what allows `Article Processing Unit of Work`'s failure to be captured cleanly by `asyncio.gather(..., return_exceptions=True)` (research.md item 6).

## Non-goals

- No connection pool sizing decision is fixed by this contract — `create_async_engine(..., pool_size=..., max_overflow=...)` tuning is an implementation-time decision (mirrors how `chatbot_plugin_sdk`'s `AsyncPgBackend` picks its own defaults; this pipeline's async engine is independent of that one and can tune separately).
- No migration of the *other* jobs' repositories (weekly report, metrics-refresh, dedup-reconciliation, RAG-backfill) to async — explicitly out of scope (spec.md Assumptions; plan.md Complexity Tracking).
