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

from src.utils.logging import get_logger, bind_correlation_id, configure_logging
from src.config.settings import SENTRY_DSN
from src.infrastructure.http.http_client import HttpClient, init_default_client
from src.database import init_db
from src.infrastructure.observability.otel_metrics import SCRAPER_RUNS, SCRAPER_DURATION, push_metrics
from src.infrastructure.observability.run_context import init_run_context, get_run_id
from src.infrastructure.observability.run_summary import RunSummary
from src.notifications.service import notify_all

if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)

logger = get_logger(__name__)

MAX_EXECUTION_TIME = 50 * 60  # 50 minutes

_shutdown_requested = False


def signal_handler(signum, frame):
    global _shutdown_requested
    logger.warning("shutdown_signal_received", signal=signum)
    _shutdown_requested = True


def check_timeout(start_time: float) -> bool:
    elapsed = time.time() - start_time
    if elapsed >= MAX_EXECUTION_TIME:
        logger.warning("execution_timeout_reached", elapsed_seconds=elapsed)
        return True
    return False


def load_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "analysis.txt")
    with open(prompt_path, "r") as f:
        return f.read()


def main() -> None:
    from opentelemetry import trace as otel_trace
    from src.infrastructure.observability.otel_tracing import get_tracer, shutdown_tracing
    from src.app.composition_root import build_run_scraper_use_case

    configure_logging()

    # Randomise start time to avoid hitting arXiv at the top of the hour
    # alongside other cron jobs. Skipped when RUN_IMMEDIATELY=1 (manual triggers).
    if not os.environ.get("RUN_IMMEDIATELY"):
        _jitter = random.uniform(0, 900)  # 0–15 minutes
        logger.info("startup_jitter_sleep", seconds=round(_jitter))
        time.sleep(_jitter)

    init_default_client(HttpClient.build_default())
    SCRAPER_RUNS.add(1)

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("execution_started", run_id=run_id, correlation_id=correlation_id)

    init_db()
    start_time = time.time()
    summary = RunSummary()

    tracer = get_tracer()
    with tracer.start_as_current_span("scraper.run") as span:
        span.set_attribute("run.id", run_id)
        span.set_attribute("run.correlation_id", correlation_id)

        try:
            prompt = load_prompt()
            run_uc = build_run_scraper_use_case(prompt=prompt, summary=summary)
            run_uc.execute(correlation_id=correlation_id, summary=summary)

        except Exception as e:
            span.record_exception(e)
            span.set_status(otel_trace.StatusCode.ERROR, str(e))
            logger.error("execution_failed", error=str(e))
            raise
        finally:
            duration = time.time() - start_time
            logger.info(
                "execution_completed",
                run_id=get_run_id(),
                duration_seconds=duration,
            )
            SCRAPER_DURATION.record(duration)
            notify_all(summary, duration)
            try:
                push_metrics()
            except Exception as e:
                logger.warning("push_metrics_failed", error=str(e))
            shutdown_tracing()


if __name__ == "__main__":
    main()
