[![src unit coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=unit)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=unit)
[![src integration coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=integration)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=integration)
![unit tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/unit-passrate.json)
![integration tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/integration-passrate.json)

# Scraper / Analyzer Service

Standalone Python service that discovers articles, fetches content, analyzes them with LLM providers, and normalizes tags with embeddings. Runs on a schedule (cron or Railway job) and writes results directly to the shared PostgreSQL database.

## Architecture

Follows **Hexagonal Architecture / Domain-Driven Design**. Dependencies point inward: Infrastructure → Application → Domain.

![Clean Architecture](../drawio/clean_architecture.png)

```
src/
├── bootstrap.py                    # Dependency assembly (replaces composition_root.py)
├── config/
│   └── settings.py                 # App config: SENTRY_DSN, TRANSLATION_LANGUAGES, etc.
├── entrypoints/
│   └── cli/
│       ├── main.py                 # Scheduled scrape→analyze→translate→RAG pipeline (logging, OTel, Sentry, jitter, 50-min timeout)
│       ├── translate.py            # Standalone translation entrypoint
│       ├── backfill_rag.py         # RAG vector backfill for articles missing chunks
│       ├── refresh_metrics.py      # Recurring citation-metric refresh (OpenAlex / Semantic Scholar)
│       ├── weekly_report.py        # Per-topic weekly report generation
│       └── dedup_reconcile.py      # Reconcile OpenAlex articles deduped after scrape
├── modules/                        # Domain-Driven Design bounded contexts
│   ├── collection/                 # Article discovery & ingestion
│   │   ├── domain/                 # Entities: ScrapeJob, ArxivMetadata, ScraperSetting
│   │   │   ├── entities/           #   Value objects: ScrapedArticle, ScraperKeyword, URL
│   │   │   ├── repositories/       #   Interfaces: IScraperSettingRepository, IArxivMetadataRepository
│   │   │   └── services/           #   DedupService, Scraper (abstract)
│   │   └── application/
│   │       ├── use_cases/          #   ProcessScrapedArticleUseCase, PipelineStats
│   │       ├── event_handlers/     #   ArticleScrapedHandler
│   │       └── events/             #   ArticleScrapedEvent, PipelineCompletedEvent
│   ├── intelligence/               # LLM analysis, translation, tag normalization
│   │   ├── domain/                 # Entities: Analysis, AnalysesContent, TagNormalizationSuggestion
│   │   │   ├── repositories/       #   Interfaces for analysis, tags, translations
│   │   │   └── services/           #   ILLMService, IEmbeddingService
│   │   └── application/
│   │       ├── use_cases/          #   AnalyzeArticleUseCase, TranslateArticleUseCase,
│   │       │                       #   TranslateTagsUseCase, NormalizeTagsUseCase
│   │       ├── event_handlers/     #   ArticleProcessedHandler, AnalysisCompletedHandler,
│   │       │                       #   TagNormalizationHandler, FailedTaskPersistenceHandler
│   │       └── events/             #   AnalysisCompletedEvent, TagNormalizationCompletedEvent, etc.
│   └── shared/                     # Cross-module domain objects
│       └── domain/
│           └── entities/           #   Article, Topic
├── shared/                         # Cross-cutting application concerns
│   ├── domain/
│   │   ├── entities/               #   Article, Topic (root aggregates)
│   │   └── repositories/           #   IArticleRepository, ITopicRepository, IFailedTaskRepository
│   ├── application/
│   │   ├── events/                 #   ArticleProcessedEvent, FailedEvent
│   │   └── ports/                  #   IEventBus
│   └── logging.py                  # structlog façade (get_logger)
└── infrastructure/                 # Technical implementations
    ├── collection/
    │   ├── scrapers/               #   RssScraper, BlogScraper, ArxivScraper,
    │   │                           #   OpenAlexScraper, SemanticScholarScraper
    │   │                           #   (all extend BaseScraper)
    │   ├── clients/                #   RssClient, ArxivClient,
    │   │                           #   OpenAlexClient, SemanticScholarClient
    │   ├── parsers/                #   HtmlParser, PdfParser, SanitizeService
    │   ├── executor/               #   ScrapeExecutor (5 workers, per-host semaphore,
    │   │                           #   robots.txt respect), DiscoverTask, FetchTask
    │   └── collection_pipeline.py  #   CollectionPipeline.run()
    ├── intelligence/
    │   ├── llm/
    │   │   ├── providers/          #   GeminiProvider, ClaudeProvider, OpenRouterProvider
    │   │   ├── embedding/          #   GeminiEmbeddingProvider
    │   │   ├── rate_limit/         #   SlidingWindowStrategy, NoOpStrategy, ProviderSelector
    │   │   └── resilient_llm_service.py  # Ordered provider fallback — sync (ResilientLLMService) + async (AsyncResilientLLMService, capacity-aware) siblings
    │   └── prompt/
    │       └── prompt_factory.py   #   ConcretePromptFactory (analysis, translation, tag prompts)
    ├── persistence/
    │   ├── shared/                 #   SqlAlchemyArticleRepository, TopicRepository, FailedTaskRepository
    │   ├── collection/             #   SqlAlchemyScraperSettingRepository, ArxivMetadataRepository
    │   ├── intelligence/           #   SqlAlchemyAnalysisRepository, TagRepository,
    │   │                           #   TagGroupDefinitionRepository, translation repos
    │   └── database.py             #   sync NullPool (get_session, batch/cron jobs) + async bounded QueuePool
    │                               #   (get_async_sessionmaker, prewarm/dispose — the concurrent pipeline)
    └── shared/
        ├── events/                 #   InMemoryEventBus (sync) + AsyncInMemoryEventBus (per-article, run-level)
        ├── http/                   #   HttpClient, rate_limiter, retry, proxy, user_agent
        ├── logging.py              #   configure_logging(), bind_correlation_id()
        ├── notifications/          #   NotificationService, TelegramNotifier
        └── observability/          #   OTel tracing, Loki log shipping, GeoIP
```

## Pipeline Event Flow

`CollectionPipeline.run()` is `async`. Discover / fetch / pre-dedup stay **batched and sequential** (024-async-pipeline-refactor FR-003); from Publish onward **every article runs in its own `asyncio.Task`** with its own `AsyncSession` and its own fresh `AsyncInMemoryEventBus` (built per-article by `bootstrap.py`), so one article's chain never blocks another's. Completion is reported by **two barriers**, not one.

```
CollectionPipeline.run()
  │
  ├─ Discover (batched)  — ScrapeExecutor.run_discover() → scrapers' discover() → List[ScrapeJob]
  ├─ Pre-dedup           — drop URLs already analyzed (UrlHash), as a pre-fetch filter
  ├─ Fetch   (batched)   — ScrapeExecutor.run_fetch_only() (5 workers, per-host BoundedSemaphore(1)) → ScrapedArticle
  ├─ Post-dedup          — collapse within-batch dupes + re-check already-analyzed
  │
  ├─ [per article — own asyncio.Task, own AsyncSession, own AsyncInMemoryEventBus,
  │   bounded by TEXT_STAGE_CONCURRENCY]
  │    ├─ publish ArticleScrapedEvent
  │    │    └─ ProcessScrapedArticleUseCase (dedup + save Article + ArxivMetadata + free metric seeds)
  │    │         └─ publish ArticleProcessedEvent
  │    │              ├─ dispatch_rag → AsyncRagIngestionHandler as a DETACHED asyncio.Task
  │    │              │   (never awaited inline; bounded by RAG_DISPATCH_CONCURRENCY; RPD circuit breaker;
  │    │              │    RAG_INGEST_TIMEOUT_SECONDS backstop) — tracked for Barrier 2
  │    │              └─ AnalyzeArticleUseCase (LLM chain → tags + analysis)
  │    │                   └─ publish AnalysisCompletedEvent  (or AnalysisFailedEvent)
  │    ├─ TagNormalizationHandler (on AnalysisCompletedEvent)
  │    │    └─ NormalizeTagsUseCase (embedding similarity → TagNormalizationSuggestion)
  │    │         └─ publish TagNormalizationCompletedEvent  (or TagNormalizationFailedEvent)
  │    ├─ AnalysisCompletedHandler (on TagNormalizationCompletedEvent)
  │    │    └─ TranslateArticleUseCase + TranslateTagsUseCase (for configured TRANSLATION_LANGUAGES)
  │    │         └─ publish TranslationCompletedEvent  (or TranslationFailedEvent)
  │    └─ FailedTaskPersistenceHandler — saves FailedTask on any *FailedEvent
  │
  ├─ Barrier 1: every article's text-stage Task has settled (asyncio.gather, return_exceptions=True)
  │    └─ publish TextPipelineCompletedEvent
  │         ├─ SearchIndexRebuildHandler  (RebuildSearchIndexUseCase → Redis search index)
  │         ├─ CacheInvalidationHandler
  │         └─ CacheWarmupHandler          (strictly after invalidation)
  │
  └─ Barrier 2: every detached RAG Task has also settled
       └─ publish PipelineCompletedEvent
            ├─ OtelMetricsHandler   (push counters/histograms to Grafana Cloud)
            └─ NotificationHandler  (Telegram summary, incl. partial-failure count + rate-limited hosts/providers)
```

The `article.pipeline` span per article is kept open (via `_ArticleSpanLatch`) until **both** its text stage and its detached RAG Task have settled, so its subtree contains `article.rag_ingest`. Barrier-1 handlers only depend on text content, so they don't wait on RAG.

## Scrapers

| Scraper | Source | Discovery method |
|---|---|---|
| `RssScraper` | RSS/Atom feeds | `RssClient` — parses feed entries |
| `BlogScraper` | Blog URLs | CSS-selector crawl via `HtmlParser` |
| `ArxivScraper` | arXiv API | `ArxivClient` — keyword + category search |
| `OpenAlexScraper` | OpenAlex API | `OpenAlexClient` — keyword search, tracks `original_source` + `primary_topic` |
| `SemanticScholarScraper` | Semantic Scholar API | `SemanticScholarClient` — keyword search, tracks `original_source`, `paper_id` |

All scrapers extend `BaseScraper` and implement `discover() → List[ScrapeJob]` and `fetch(job) → ScrapedArticle`. The `ConcreteScraperFactory` selects the correct scraper based on `ScraperSetting.source_type`.

`ScrapeExecutor` runs concurrent fetches with 5 workers, a per-host semaphore, and respects `robots.txt` for blog sources.

## LLM Provider Configuration

Providers are loaded at startup from the **`llm_providers` database table** (managed via `/admin/llm-providers` in the frontend). Each row specifies name, model, `api_key_env`, priority, `is_active`, and rate limits (`rpm`/`tpm`/`rpd`).

`ResilientLLMService` holds an ordered list of `ProviderHandler` objects sorted by priority. On `analyze()`, it walks providers in priority order and falls back on `RateLimitExhausted` or any exception. `SlidingWindowStrategy` enforces per-window RPM/TPM/RPD limits. The concurrent pipeline uses the async sibling `AsyncResilientLLMService`, which additionally scans for a provider with spare capacity (`ProviderSelector`) before dispatching so concurrent article tasks spread across every model with headroom.

`ResilientEmbeddingService` follows the same pattern for embedding providers (currently `GeminiEmbeddingProvider`). Tag embeddings (`vector(768)`) live on the `tags` table via pgvector and feed `NormalizeTagsUseCase`'s dedup suggestions. RAG ingestion is separate: dense/sparse embeddings for article chunks (`vectors` schema, migration 21) are produced by the RAG SDK's own provider stack, configured via `RAG_DENSE_*` / `RAG_SPARSE_*` env vars, and written on a detached per-article task (Barrier 2).

## Process Lifecycle (`main.py`)

1. `validate_config()` — asserts required env vars are set
2. `configure_logging()` — structlog + Loki handler attach
3. **Startup jitter** — random 0–180 s sleep (skip with `RUN_IMMEDIATELY=1`)
4. `init_default_client()` — shared `HttpClient` with retry/proxy
5. `init_run_context()` — generates `run_id` + `correlation_id`; bound to every log entry
6. **OTel root span** `scraper.run` wraps `build_collection_pipeline()` + `pipeline.run()`
7. On completion — logs per-source stats (new / duplicate / failed articles)
8. `shutdown_tracing()` — flushes `BatchSpanProcessor` after root span ends

Hard timeout: **50 minutes**, enforced by `asyncio.timeout(MAX_EXECUTION_TIME)` around `pipeline.run()` (cancels the run, disposes the async engine, still flushes final telemetry). No custom signal handlers — SIGTERM terminates directly, platform SIGKILL is the backstop.

## Observability

| Concern | Implementation |
|---|---|
| Traces | OpenTelemetry → Grafana Cloud (OTLP) |
| Logs | structlog → Grafana Loki (fire-and-forget POST) |
| Metrics | OTel counters/histograms pushed on `PipelineCompletedEvent` |
| Errors | Sentry SDK (optional, graceful no-op if `SENTRY_DSN` unset) |
| Geo | MaxMind GeoIP2 (`MAXMIND_LICENSE_KEY`) |

## Deployment

| Context | File |
|---|---|
| Production | `Dockerfile` (multi-stage, `uv` for dependency install) |
| Development | `Dockerfile.dev` (hot-reload) |
| Deploy config | `.railway/railway.ts` (`railway config plan/apply`) — cron schedule, env vars, restart policy. `railway.toml` no longer holds service config. |

Required environment variables: `DATABASE_URL`, one or more LLM API keys (configured via `api_key_env` in `llm_providers` table), `TELEGRAM_BOT_TOKEN`. Optional: `SENTRY_DSN`, `MAXMIND_LICENSE_KEY`. RAG ingestion is enabled when `VECTOR_DB_*` are set and configured via `RAG_DENSE_*` / `RAG_SPARSE_*`; async-pipeline concurrency via `TEXT_STAGE_CONCURRENCY`, `RAG_DISPATCH_CONCURRENCY`, `ASYNC_DB_POOL_SIZE`, `PIPELINE_EXECUTOR_MAX_WORKERS` (see `src/config/settings.py`).
