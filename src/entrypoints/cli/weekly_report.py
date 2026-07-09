"""
Weekly report CLI entrypoint.

Usage:
    uv run python -m src.entrypoints.cli.weekly_report
    uv run python -m src.entrypoints.cli.weekly_report --topic-id <uuid> --week-start 2025-01-06

Architecture:
    - Domain: WeeklyReport entity, WeeklyReportTranslation entity,
      WeeklyReportRepository + WeeklyReportTranslationRepository interfaces,
      ImageGenerationService + TranslationService ports.
    - Application: GenerateWeeklyReportUseCase (LLM summary + image + i18n +
      notifications), TranslateWeeklyReportUseCase.
    - Infrastructure: WeeklyReportPipeline (topic resolution + per-topic
      orchestration), image provider factory (Gemini Imagen | HuggingFace).
    - Bootstrap: build_weekly_pipeline() assembles dependencies and uses
      TRANSLATION_LANGUAGES to drive per-language translation of title +
      summary_text into weekly_reports_translation.

i18n: title + summary_text are produced in English, then translated into each
language configured via TRANSLATION_LANGUAGES. Notifications continue to use
the English fields; per-user locale rendering is handled in the notification
content builders.
"""
import argparse
import signal
import time
from datetime import date, timedelta
from uuid import UUID

from src.config.settings import APP_ENV, SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.observability import init_run_context, get_run_id


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN)

logger = get_logger(__name__)

_shutdown_requested = False


def signal_handler(signum, frame):
    """Sets the shutdown flag when SIGTERM or SIGINT is received."""
    global _shutdown_requested
    logger.warning("shutdown_signal_received", signal=signum)
    _shutdown_requested = True


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def main() -> None:
    """Entry point: wires dependencies and runs weekly report generation for due topics."""
    from opentelemetry import trace as otel_trace
    from src.infrastructure.shared.observability import get_tracer, shutdown_tracing
    from shared.enums.observability import SpanName, SpanAttribute

    parser = argparse.ArgumentParser(description="Generate weekly article summary reports")
    parser.add_argument("--topic-id", type=str, default=None, help="Generate report only for this topic UUID")
    parser.add_argument("--week-start", type=str, default=None, help="Week start date (YYYY-MM-DD, must be Monday)")
    args = parser.parse_args()

    validate_config()
    configure_logging()

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    week_start = (
        date.fromisoformat(args.week_start)
        if args.week_start
        else _monday_of_week(date.today() - timedelta(days=7))
    )
    topic_id = UUID(args.topic_id) if args.topic_id else None

    env = APP_ENV
    logger.info(
        "execution_started",
        run_id=run_id,
        correlation_id=correlation_id,
        env=env,
        week_start=str(week_start),
    )

    start_time = time.time()
    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            session = None
            reports = []
            try:
                from src.bootstrap import build_weekly_pipeline
                pipeline, session = build_weekly_pipeline()
                reports = pipeline.run(week_start=week_start, topic_id=topic_id)
            except Exception as e:
                span.record_exception(e)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                logger.error("execution_failed", error=str(e), error_type=type(e).__name__)
                raise
            finally:
                duration = time.time() - start_time
                logger.info(
                    "execution_completed",
                    run_id=get_run_id(),
                    duration_seconds=round(duration, 2),
                    reports_generated=len(reports),
                )
                if session is not None:
                    session.close()
        # with block exits here → span.end() is called → queued for export
    finally:
        shutdown_tracing()  # flush BatchSpanProcessor only after root span is queued


if __name__ == "__main__":
    main()
