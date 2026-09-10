"""
Entry point — frequency-based scrape dispatch.

Responsibilities here:
  - Process-level setup (logging, HTTP client, OTel, Sentry)
  - Timeout guard (asyncio.timeout around pipeline.run())
  - Wiring composition root → RunScraperUseCase
  - Observability teardown (metrics push, tracing shutdown, notifications)

All domain/application logic lives in src/app/ and src/ingestion/.
"""
import asyncio
import time
import random

from src.config.settings import APP_ENV, SENTRY_DSN, validate_config, get_run_immediately
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.http import HttpClient, init_default_client
from src.infrastructure.shared.observability import (
    init_run_context, get_run_id, log_execution_started, log_execution_completed,
)


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1, include_local_variables=False)

logger = get_logger(__name__)

MAX_EXECUTION_TIME = 50 * 60  # 50 minutes — enforced by asyncio.timeout() in main()


def main() -> None:
    """Entry point: wires dependencies, applies startup jitter, runs the scrape pipeline, and flushes telemetry."""
    from opentelemetry import trace as otel_trace
    from src.infrastructure.shared.observability import get_tracer, shutdown_tracing
    from src.bootstrap import build_collection_pipeline

    validate_config()
    configure_logging()

    # Randomise start time to avoid hitting arXiv at the top of the hour
    # alongside other cron jobs. Skipped when RUN_IMMEDIATELY is set (manual triggers).
    jitter_seconds = None
    if not get_run_immediately():
        jitter_seconds = random.uniform(0, 180)  # 0–3 minutes
        logger.info("startup_jitter_sleep", seconds=round(jitter_seconds))
        time.sleep(jitter_seconds)

    init_default_client(HttpClient.build_default())

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    started_at, t0 = log_execution_started(
        logger, run_id=run_id, correlation_id=correlation_id, jitter_seconds=jitter_seconds,
    )

    tracer = get_tracer()
    from shared.enums.observability import SpanName, SpanAttribute
    try:
        with tracer.start_as_current_span(SpanName.SCRAPER_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            # 024-async-pipeline-refactor: build_collection_pipeline() and
            # CollectionPipeline.run() are both async now — asyncio.run() is
            # the single bridge point from this otherwise-synchronous
            # entrypoint into the pipeline's event loop (research.md item 9).
            # pipeline_stats is assigned as soon as the *build* step succeeds
            # (via the mutable holder below), independent of whether the
            # subsequent .run() call later fails — matching the original
            # sync code's two-separate-statements behavior, where a failure
            # in pipeline.run() alone still left pipeline_stats bound for the
            # finally block below.
            pipeline_stats = None

            async def _build_and_run():
                nonlocal pipeline_stats
                from concurrent.futures import ThreadPoolExecutor
                from src.config.settings import PIPELINE_EXECUTOR_MAX_WORKERS
                from src.infrastructure.persistence.database import dispose_async_engine

                # asyncio.getaddrinfo — every asyncpg cold connect's DNS lookup —
                # and every asyncio.to_thread call run on the loop's default
                # executor. Its default size (~min(32, cpu+4), i.e. ~5-6 on a
                # small Railway container) is starved by a run-start connection
                # burst across the scraper + RAG SDK pools, so queued getaddrinfo
                # calls miss asyncpg's connect timeout. Give it real room.
                asyncio.get_running_loop().set_default_executor(
                    ThreadPoolExecutor(
                        max_workers=PIPELINE_EXECUTOR_MAX_WORKERS,
                        thread_name_prefix="pipeline-aio",
                    )
                )
                try:
                    pipeline, pipeline_stats = await build_collection_pipeline(jitter_seconds=jitter_seconds)
                    # Hard wall-clock cap on the pipeline run itself. asyncio.timeout()
                    # cancels pipeline.run() in place on expiry; the `finally` below
                    # still disposes the engine cleanly inside this same event loop,
                    # and main()'s outer `finally` still flushes pipeline_stats
                    # telemetry. The platform's own SIGKILL is the backstop if the
                    # run doesn't unwind promptly; startup jitter (<=180s) is
                    # deliberately not counted against this budget.
                    try:
                        async with asyncio.timeout(MAX_EXECUTION_TIME):
                            await pipeline.run()
                    except TimeoutError:
                        logger.warning(
                            "execution_timeout_reached",
                            timeout_seconds=MAX_EXECUTION_TIME,
                        )
                        raise
                finally:
                    # Close the async engine's pooled connections inside this same
                    # event loop, before asyncio.run() tears it down.
                    await dispose_async_engine()

            try:
                asyncio.run(_build_and_run())

            except Exception as e:
                span.record_exception(e)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                logger.error("execution_failed", error=str(e), error_type=type(e).__name__)
                raise
            finally:
                stats = pipeline_stats.get_results()
                total_new = sum(s.new for s in stats)
                total_dup = sum(s.duplicate for s in stats)
                total_fail = sum(s.failed for s in stats)
                per_source = {s.source: {"new": s.new, "duplicate": s.duplicate, "failed": s.failed} for s in stats}
                log_execution_completed(
                    logger, started_at, t0,
                    run_id=get_run_id(),
                    articles_new=total_new,
                    articles_duplicate=total_dup,
                    articles_failed=total_fail,
                    articles_found=total_new + total_dup,
                    sources=per_source,
                )
        # with block exits here → span.end() is called → queued for export
    finally:
        shutdown_tracing()  # flush BatchSpanProcessor only after root span is queued


if __name__ == "__main__":
    main()
