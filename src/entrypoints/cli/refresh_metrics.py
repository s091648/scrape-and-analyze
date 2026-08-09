"""
Recurring metric refresh CLI entrypoint — keeps catalog-defined recommendation
signals (citation_count today; future impact_factor/h-index) fresh for
previously-scraped articles, independent of the initial scrape.

Usage:
    uv run python -m src.entrypoints.cli.refresh_metrics
    uv run python -m src.entrypoints.cli.refresh_metrics --limit 200

Deployed as its own Railway Cron Service (see src/railway.toml), separate from
both the weekly report runner and the backend's view_count Redis flush —
research.md §9b explains why these three don't share a runner.

Architecture:
    - Domain: MetricExtractor interface (src/modules/collection/domain/services/).
    - Infrastructure: ResilientMetricsService, JsonPathMetricExtractor
      (src/infrastructure/collection/metrics/), generalized
      ArticleMetricsRepository.upsert().
    - Bootstrap: build_metrics_refresh_pipeline() reads the metric_definitions
      catalog from DB and wires the fetcher registry.

Concurrency:
    Each article's fetch_all() call is wrapped as a coroutine and run via
    asyncio.gather() under a semaphore (--concurrency, default 5). The actual
    HTTP call is still the synchronous, blocking ResilientMetricsService /
    HttpClient stack, so each one runs inside asyncio.to_thread() rather than
    truly asynchronously — this doesn't bypass the per-domain rate limiter in
    src/infrastructure/shared/http/rate_limiter.py (api.semanticscholar.org
    is capped at 1 RPM there deliberately, to stay under its unauthenticated
    daily quota — see that module's docstring), so articles resolved via that
    single provider still queue up at ~1/min regardless of concurrency. What
    concurrency *does* buy: articles going through a different, less-limited
    provider/domain (e.g. api.openalex.org at 5 RPM) are no longer blocked
    behind a whole fetch+DB round trip for an unrelated article stuck waiting
    on the semantic_scholar bucket. The DB upsert per article is deliberately
    left as a plain synchronous call (not offloaded to a thread) so it never
    executes concurrently with another article's upsert on the one shared,
    non-thread-safe SQLAlchemy session from build_metrics_refresh_pipeline().
"""
import argparse
import asyncio
import time

from src.config.settings import APP_ENV, SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.http import HttpClient, init_default_client
from src.infrastructure.shared.observability import init_run_context


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1, include_local_variables=False)

logger = get_logger(__name__)


async def _refresh_one(row, metrics_service, metrics_repo, semaphore: asyncio.Semaphore) -> bool | None:
    """Refresh metrics for one article. Returns True (refreshed), False (fetch or
    upsert raised), or None (no identifiers to look up, or the provider chain
    found nothing — neither counts as a failure, matching prior behavior)."""
    article_id, metadata = row.article_id, row.metadata or {}
    identifiers = {
        k: v for k, v in {"doi": metadata.get("doi"), "arxiv_id": metadata.get("arxiv_id")}.items()
        if v
    }
    if not identifiers:
        return None

    async with semaphore:
        try:
            # fetch_all() is the synchronous, rate-limited HTTP stack — offload to a
            # worker thread so other articles' fetches can run while this one is
            # blocked in the per-domain rate limiter's token-bucket wait.
            metrics = await asyncio.to_thread(metrics_service.fetch_all, identifiers)
        except Exception as e:
            logger.warning("article_metrics_refresh_failed", article_id=str(article_id), error=str(e))
            return False

    if not metrics:
        return None

    try:
        # Deliberately NOT offloaded to a thread — see module docstring: this keeps
        # every upsert on the event-loop thread, so the one shared, non-thread-safe
        # SQLAlchemy session is never touched by two articles at once.
        metrics_repo.upsert(article_id, metrics)
    except Exception as e:
        logger.warning("article_metrics_refresh_failed", article_id=str(article_id), error=str(e))
        return False

    logger.info("article_metrics_refreshed", article_id=str(article_id), metrics=list(metrics.keys()))
    return True


async def _refresh_all(rows, metrics_service, metrics_repo, concurrency: int) -> tuple[int, int]:
    """Refresh metrics for all rows concurrently (bounded by `concurrency`) and
    return (refreshed_count, failed_count)."""
    semaphore = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(*(
        _refresh_one(row, metrics_service, metrics_repo, semaphore) for row in rows
    ))
    refreshed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    return refreshed, failed


def main() -> None:
    """CLI entry point: refreshes catalog-defined metrics for stale articles."""
    from opentelemetry import trace as otel_trace
    from src.infrastructure.shared.observability import get_tracer, shutdown_tracing
    from shared.enums.observability import SpanName, SpanAttribute

    parser = argparse.ArgumentParser(description="Refresh recommendation-signal metrics (citation_count, etc.)")
    parser.add_argument("--limit", type=int, default=200, help="Max number of articles to refresh per run")
    parser.add_argument("--concurrency", type=int, default=5,
                         help="Max number of articles refreshed concurrently (default 5; see module docstring)")
    args = parser.parse_args()

    validate_config()
    configure_logging()
    init_default_client(HttpClient.build_default())

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    start_time = time.time()
    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(SpanName.REFRESH_METRICS_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            session = None
            try:
                from src.bootstrap import build_metrics_refresh_pipeline
                metrics_service, metrics_repo, session, event_bus = build_metrics_refresh_pipeline()

                enabled_metric_keys = metrics_service.tracked_metric_keys
                if not enabled_metric_keys:
                    logger.warning("no_enabled_metric_definitions")
                    print("No enabled metric definitions found — nothing to refresh")
                    return

                rows = metrics_repo.find_stale(enabled_metric_keys, args.limit)
                logger.info("stale_articles_found", count=len(rows), metric_keys=enabled_metric_keys)

                refreshed, failed = asyncio.run(
                    _refresh_all(rows, metrics_service, metrics_repo, args.concurrency)
                )

                logger.info("metrics_refresh_completed", total=len(rows), refreshed=refreshed, failed=failed)
                print(f"Metrics refresh complete: {refreshed}/{len(rows)} articles refreshed ({failed} failed)")

                from src.modules.collection.application.events import MetricsRefreshCompletedEvent
                event_bus.publish(MetricsRefreshCompletedEvent(
                    total=len(rows), refreshed=refreshed, failed=failed,
                    duration_seconds=time.time() - start_time,
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
