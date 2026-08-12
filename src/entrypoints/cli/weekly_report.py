"""
Weekly report CLI entrypoint.

Usage:
    uv run python -m src.entrypoints.cli.weekly_report
    uv run python -m src.entrypoints.cli.weekly_report --topic-id <uuid> --week-start 2025-01-06
    uv run python -m src.entrypoints.cli.weekly_report --week-start 2025-01-06 --force

Dedup: week_start is always normalized to that week's Monday, and
GenerateWeeklyReportUseCase skips regeneration (returning the existing row)
when a completed report already exists for the same (topic_id, week_start),
unless --force is passed.

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
from datetime import date, timedelta
from uuid import UUID

from src.config.settings import APP_ENV, SENTRY_DSN, validate_config
from src.shared.logging import get_logger
from src.infrastructure.shared.logging import bind_correlation_id, configure_logging
from src.infrastructure.shared.observability import (
    init_run_context, get_run_id, log_execution_started, log_execution_completed,
)


if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1, include_local_variables=False)

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
    parser.add_argument(
        "--week-start", type=str, default=None,
        help="Any date within the target week (YYYY-MM-DD); normalized to that week's Monday",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate and overwrite even if a completed report already exists for this topic/week",
    )
    args = parser.parse_args()

    validate_config()
    configure_logging()

    run_id, correlation_id = init_run_context()
    bind_correlation_id(correlation_id)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    week_start = (
        _monday_of_week(date.fromisoformat(args.week_start))
        if args.week_start
        else _monday_of_week(date.today() - timedelta(days=7))
    )
    topic_id = UUID(args.topic_id) if args.topic_id else None

    started_at, t0 = log_execution_started(
        logger, run_id=run_id, correlation_id=correlation_id, week_start=str(week_start),
    )

    tracer = get_tracer()
    try:
        with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_RUN) as span:
            span.set_attribute(SpanAttribute.RUN_ID, run_id)
            span.set_attribute(SpanAttribute.CORRELATION_ID, correlation_id)

            session = None
            event_bus = None
            llm_service = None
            reports = []
            total_topics = 0
            try:
                from src.bootstrap import build_weekly_pipeline
                pipeline, session, event_bus, llm_service = build_weekly_pipeline()
                reports, total_topics = pipeline.run(week_start=week_start, topic_id=topic_id, force=args.force)
            except Exception as e:
                span.record_exception(e)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                logger.error("execution_failed", error=str(e), error_type=type(e).__name__)
                raise
            finally:
                failed = total_topics - len(reports)
                rate_limited_providers = tuple(
                    getattr(llm_service, "exhausted_providers", []) if llm_service is not None else []
                )
                execution = log_execution_completed(
                    logger, started_at, t0,
                    run_id=get_run_id(),
                    reports_generated=len(reports),
                    topics_processed=total_topics,
                    topics_failed=failed,
                    rate_limited_providers=rate_limited_providers,
                )
                if event_bus is not None:
                    from src.modules.intelligence.application.events import WeeklyReportJobCompletedEvent
                    event_bus.publish(WeeklyReportJobCompletedEvent(
                        total_topics=total_topics, generated=len(reports), failed=failed,
                        execution=execution,
                        rate_limited_providers=rate_limited_providers,
                    ))
                if session is not None:
                    session.close()
        # with block exits here → span.end() is called → queued for export
    finally:
        shutdown_tracing()  # flush BatchSpanProcessor only after root span is queued


if __name__ == "__main__":
    main()
