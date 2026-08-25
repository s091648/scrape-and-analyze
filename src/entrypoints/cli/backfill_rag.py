"""
Recurring RAG-backfill CLI entrypoint — ingests previously-scraped articles
into the vector store that predate the RAG feature (or that failed ingestion
at scrape time), independent of the live scrape pipeline.

Usage:
    uv run python -m src.entrypoints.cli.backfill_rag
    uv run python -m src.entrypoints.cli.backfill_rag --limit 500

Deployed as its own Railway Cron Service (see src/railway.toml), separate
from the scraper worker, refresh-metrics, and dedup-reconcile.

Component reuse:
    build_rag_backfill_pipeline() (src/bootstrap.py) reuses
    build_async_rag_ingestion_service() — the exact same AsyncRagSdkIngestionService
    construction build_collection_pipeline() wires into the live scrape
    pipeline — wrapped in the same AsyncIngestArticleForRagUseCase the real-time
    AsyncRagIngestionHandler calls (024-async-pipeline-refactor US6, research.md
    item 11 — previously the sync build_rag_ingestion_service()/IngestArticleForRagUseCase).
    Backfilled articles are therefore chunked and embedded identically to
    freshly-scraped ones; this script only supplies a different source of
    candidates (a DB query) and a different trigger (cron instead of
    ArticleProcessedEvent).

Candidate selection:
    public.articles.has_vectors is a denormalised flag kept in sync by a
    Postgres trigger on INSERT into vectors.articles (see migration
    21_add_vectors_schema_and_article_chunks) — so "pending backfill" is just
    has_vectors = FALSE (RagBackfillRepository.find_pending). There is no
    separate retry-tracking: an article that fails ingestion simply stays
    has_vectors = FALSE and is picked up again on the next run, the same way
    refresh_metrics.py's stale-check re-evaluates every run.

    full_text is intentionally omitted when calling execute() — the
    PDF-extracted full text used at scrape time for arxiv/openalex sources
    only ever lives in-memory during the event pipeline and is never
    persisted (see IngestArticleForRagUseCase's docstring). execute() already
    falls back to assembling text from the persisted title/content/metadata
    sections when full_text is empty — exactly the case here, so no new
    fallback logic was needed for backfill.

Concurrency:
    024-async-pipeline-refactor US6 (research.md item 11): all concurrent
    ingestion runs on the main event loop, bounded by --concurrency (default
    5) via a plain asyncio.Semaphore — no worker threads, no per-article
    asyncio.run(). This (not just style consistency with main.py) is required
    for correctness: the RAG SDK's EmbeddingBatchCoordinator, which batches
    concurrent articles' embedding chunks against the shared rate limit, owns
    an asyncio.Queue and a worker asyncio.Task that must live on one event
    loop — the previous to_thread-per-article model gave each concurrent
    article its own event loop (via RagSdkIngestionService.ingest()'s
    internal asyncio.run()), which the coordinator can't span.

Quota sharing with main.py:
    Unlike the LLM analysis chain (ResilientLLMService) or tag embeddings
    (ResilientEmbeddingService, backfill_tag_embeddings.py), RAG's dense
    embedding provider (build_async_rag_ingestion_service() in src/bootstrap.py)
    is a single, fixed provider read from env vars — no multi-provider
    rate-limit fallback. Its RPD is also tracked independently per process,
    but both this script and main.py's real-time RagIngestionHandler draw
    against the same underlying provider-side daily quota. --limit therefore
    defaults conservatively (20) so one backfill run can't starve same-day
    real-time ingestion — tune up once real-world quota headroom across
    both is confirmed. Worst case either way is self-healing regardless:
    an article that fails ingestion (real-time or backfill) just stays
    has_vectors = FALSE and is retried on the next backfill run.
"""
import argparse
import asyncio

from src.config.settings import APP_ENV, SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.http import HttpClient, init_default_client
from src.infrastructure.shared.observability import (
    init_run_context, log_execution_started, log_execution_completed,
)


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1, include_local_variables=False)

logger = get_logger(__name__)


async def _backfill_one(article, use_case, semaphore: asyncio.Semaphore) -> bool:
    """Ingest one article into the vector store. Returns True on success, False
    if the use case raised."""
    async with semaphore:
        try:
            await use_case.execute(article)
        except Exception as e:
            logger.warning("article_rag_backfill_failed", article_id=str(article.id), error=str(e))
            return False

    logger.info("article_rag_backfilled", article_id=str(article.id))
    return True


async def _backfill_all(articles, use_case, concurrency: int) -> tuple[int, int]:
    """Ingest all articles concurrently (bounded by `concurrency`) and return
    (succeeded_count, failed_count)."""
    semaphore = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(*(
        _backfill_one(article, use_case, semaphore) for article in articles
    ))
    succeeded = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    return succeeded, failed


async def _run_backfill(articles, use_case, concurrency: int) -> tuple[int, int]:
    """Runs _backfill_all() then releases the RAG SDK's background worker task
    (024-async-pipeline-refactor US6, research.md item 11) — aclose() must run
    on the same event loop the coordinator's worker task was created on, so it
    has to happen inside this same asyncio.run() call, not a later one."""
    try:
        return await _backfill_all(articles, use_case, concurrency)
    finally:
        await use_case.aclose()


def main() -> None:
    """CLI entry point: ingests previously-scraped articles missing from the vector store."""
    from opentelemetry import trace as otel_trace
    from src.infrastructure.shared.observability import get_tracer, shutdown_tracing
    from shared.enums.observability import SpanName, SpanAttribute

    parser = argparse.ArgumentParser(description="Backfill RAG vector-store ingestion for existing articles")
    parser.add_argument("--limit", type=int, default=20,
                         help="Max number of articles to backfill per run (default 20 — kept low since RAG's "
                              "dense embedding provider has no multi-provider rate-limit fallback like the LLM "
                              "chain does, and shares its daily quota with main.py's real-time ingestion; tune up "
                              "once real-world quota headroom is confirmed)")
    parser.add_argument("--concurrency", type=int, default=5,
                         help="Max number of articles ingested concurrently (default 5; see module docstring)")
    args = parser.parse_args()

    validate_config()
    configure_logging()
    init_default_client(HttpClient.build_default())

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    started_at, t0 = log_execution_started(logger, run_id=run_id, correlation_id=correlation_id)

    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(SpanName.RAG_BACKFILL_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            session = None
            try:
                from src.bootstrap import build_rag_backfill_pipeline
                from src.modules.intelligence.application.events import RagBackfillCompletedEvent
                use_case, backfill_repo, session, event_bus = build_rag_backfill_pipeline()

                if use_case is None:
                    logger.warning("rag_backfill_skipped_rag_disabled")
                    execution = log_execution_completed(
                        logger, started_at, t0, run_id=run_id, total=0, succeeded=0, failed=0,
                    )
                    event_bus.publish(RagBackfillCompletedEvent(
                        total=0, succeeded=0, failed=0, execution=execution,
                    ))
                    print("RAG ingestion is disabled or misconfigured — nothing to backfill")
                    return

                articles = backfill_repo.find_pending(args.limit)
                logger.info("rag_backfill_candidates_found", count=len(articles))

                succeeded, failed = asyncio.run(
                    _run_backfill(articles, use_case, args.concurrency)
                )

                execution = log_execution_completed(
                    logger, started_at, t0,
                    run_id=run_id, total=len(articles), succeeded=succeeded, failed=failed,
                )
                print(f"RAG backfill complete: {succeeded}/{len(articles)} articles ingested ({failed} failed)")

                event_bus.publish(RagBackfillCompletedEvent(
                    total=len(articles), succeeded=succeeded, failed=failed,
                    execution=execution,
                ))
            except Exception as e:
                span.record_exception(e)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                raise
            finally:
                if session is not None:
                    session.close()
    finally:
        shutdown_tracing()


if __name__ == "__main__":
    main()
