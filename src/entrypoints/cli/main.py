"""
Entry point — frequency-based scrape dispatch.

Responsibilities here:
  - Process-level setup (logging, HTTP client, OTel, Sentry, signals)
  - Timeout guard
  - Wiring composition root → RunScraperUseCase
  - Observability teardown (metrics push, tracing shutdown, notifications)

All domain/application logic lives in src/app/ and src/ingestion/.
"""
import time
import signal
import os
import random

from src.config.settings import SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.http import HttpClient, init_default_client
from src.infrastructure.shared.observability import init_run_context, get_run_id


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN)

logger = get_logger(__name__)

MAX_EXECUTION_TIME = 50 * 60  # 50 minutes

_shutdown_requested = False


def signal_handler(signum, frame):
    """Sets the shutdown flag when SIGTERM or SIGINT is received."""
    global _shutdown_requested
    logger.warning("shutdown_signal_received", signal=signum)
    _shutdown_requested = True


def check_timeout(start_time: float) -> bool:
    """Returns True if execution has exceeded the 50-minute hard timeout."""
    elapsed = time.time() - start_time
    if elapsed >= MAX_EXECUTION_TIME:
        logger.warning("execution_timeout_reached", elapsed_seconds=elapsed)
        return True
    return False



def main() -> None:
    """Entry point: wires dependencies, applies startup jitter, runs the scrape pipeline, and flushes telemetry."""
    from opentelemetry import trace as otel_trace
    from src.infrastructure.shared.observability import get_tracer, shutdown_tracing
    from src.bootstrap import build_collection_pipeline

    validate_config()
    configure_logging()

    # Randomise start time to avoid hitting arXiv at the top of the hour
    # alongside other cron jobs. Skipped when RUN_IMMEDIATELY=1 (manual triggers).
    if not os.environ.get("RUN_IMMEDIATELY"):
        _jitter = random.uniform(0, 180)  # 0–3 minutes
        logger.info("startup_jitter_sleep", seconds=round(_jitter))
        time.sleep(_jitter)

    init_default_client(HttpClient.build_default())

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    env = os.environ.get("APP_ENV", "local")
    logger.info("execution_started", run_id=run_id, correlation_id=correlation_id, env=env)

    start_time = time.time()

    tracer = get_tracer()
    from shared.enums.observability import SpanName, SpanAttribute
    try:
        with tracer.start_as_current_span(SpanName.SCRAPER_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            try:
                pipeline, pipeline_stats = build_collection_pipeline()
                pipeline.run()

            except Exception as e:
                span.record_exception(e)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                logger.error("execution_failed", error=str(e), error_type=type(e).__name__)
                raise
            finally:
                duration = time.time() - start_time
                stats = pipeline_stats.get_results()
                total_new = sum(s.new for s in stats)
                total_dup = sum(s.duplicate for s in stats)
                total_fail = sum(s.failed for s in stats)
                per_source = {s.source: {"new": s.new, "duplicate": s.duplicate, "failed": s.failed} for s in stats}
                logger.info(
                    "execution_completed",
                    run_id=get_run_id(),
                    duration_seconds=round(duration, 2),
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
