"""
Weekly report CLI entrypoint.

Usage:
    uv run python -m src.entrypoints.cli.weekly_main
    uv run python -m src.entrypoints.cli.weekly_main --topic-id <uuid> --week-start 2025-01-06
"""
import argparse
import sys
from datetime import date, timedelta
from uuid import UUID

from src.shared.logging import get_logger

logger = get_logger(__name__)


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly article summary reports")
    parser.add_argument("--topic-id", type=str, default=None, help="Generate report only for this topic UUID")
    parser.add_argument("--week-start", type=str, default=None, help="Week start date (YYYY-MM-DD, must be Monday)")
    args = parser.parse_args()

    week_start: date
    if args.week_start:
        week_start = date.fromisoformat(args.week_start)
    else:
        week_start = _monday_of_week(date.today() - timedelta(days=7))

    try:
        from src.bootstrap import build_weekly_pipeline
        use_case, session = build_weekly_pipeline()
    except ValueError as e:
        logger.error("weekly_pipeline_build_failed", error=str(e))
        sys.exit(1)

    from models.topic import Topic

    if args.topic_id:
        topic = session.query(Topic).filter(Topic.id == UUID(args.topic_id)).first()
        if not topic:
            logger.error("topic_not_found", topic_id=args.topic_id)
            sys.exit(1)
        topics = [topic]
    else:
        topics = session.query(Topic).filter(Topic.is_active == True).all()

    if not topics:
        logger.warning("no_active_topics_found")
        return

    for topic in topics:
        try:
            report = use_case.execute(
                topic_id=topic.id,
                topic_name=topic.name,
                week_start=week_start,
            )
            logger.info("weekly_report_done", topic=topic.name, report_id=str(report.id), articles=report.article_count)
        except Exception:
            logger.exception("weekly_report_failed", topic=topic.name)

    session.close()


if __name__ == "__main__":
    main()
