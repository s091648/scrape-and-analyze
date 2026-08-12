from datetime import date
from typing import List, Optional
from uuid import UUID

from opentelemetry import trace as _otel

from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer
from src.modules.intelligence.application.use_cases.generate_weekly_report import GenerateWeeklyReportUseCase
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport
from src.shared.domain.repositories import TopicRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class WeeklyReportPipeline:
    """Resolves target topics and runs weekly report generation for each, one span per topic."""

    def __init__(
        self,
        topic_repository: TopicRepository,
        generate_use_case: GenerateWeeklyReportUseCase,
    ) -> None:
        self._topic_repository = topic_repository
        self._generate_use_case = generate_use_case

    def run(self, week_start: date, topic_id: Optional[UUID] = None, force: bool = False) -> tuple[List[WeeklyReport], int]:
        """Generate weekly reports for the given topic (or all active topics). Returns
        (reports, total_topics) — total_topics is the number of topics attempted, so
        callers can derive a failed count (total_topics - len(reports)) for their own
        job-level completion notification."""
        if topic_id is not None:
            topic = self._topic_repository.find_by_id(topic_id)
            if topic is None:
                logger.error("topic_not_found", topic_id=str(topic_id))
                return [], 0
            topics = [topic]
        else:
            topics = self._topic_repository.list_active()

        if not topics:
            logger.warning("no_active_topics_found")
            return [], 0

        tracer = get_tracer()
        reports: List[WeeklyReport] = []
        for topic in topics:
            with tracer.start_as_current_span(SpanName.WEEKLY_REPORT_TOPIC) as span:
                span.set_attribute("topic.id", str(topic.id))
                span.set_attribute("topic.name", topic.name)
                try:
                    report = self._generate_use_case.execute(
                        topic_id=topic.id,
                        topic_name=topic.name,
                        week_start=week_start,
                        force=force,
                    )
                    reports.append(report)
                    logger.info(
                        "weekly_report_done",
                        topic=topic.name,
                        report_id=str(report.id),
                        articles=report.article_count,
                    )
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(_otel.StatusCode.ERROR, str(e))
                    logger.exception("weekly_report_failed", topic=topic.name)

        return reports, len(topics)
