from opentelemetry import trace as _otel_trace
from sqlalchemy.orm import Session

from src.shared.application.ports import EventBus
from src.shared.logging import get_logger
from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    TagNormalizationCompletedEvent,
    TagNormalizationFailedEvent,
)
from src.modules.intelligence.application.use_cases import NormalizeTagsUseCase

logger = get_logger(__name__)


class TagNormalizationHandler:
    """Normalizes tags from a completed analysis and emits the result event."""

    def __init__(self, use_case: NormalizeTagsUseCase, event_bus: EventBus, session: Session) -> None:
        self._use_case = use_case
        self._event_bus = event_bus
        self._session = session

    def handle(self, event: AnalysisCompletedEvent) -> None:
        """Run tag normalization on the analysis result and publish outcome."""
        span = _otel_trace.get_current_span()
        span.set_attribute("analysis.id", str(event.analysis_id))
        span.set_attribute("article.id", str(event.article_id))
        span.set_attribute("tags.group_count", len(event.tag_groups))
        span.set_attribute("tags.total_count", sum(len(tags) for _, tags in event.tag_groups))
        span.set_attribute("tags.group_names", [g for g, _ in event.tag_groups])
        span.set_attribute("tags.tag_names", [t for _, tags in event.tag_groups for t in tags])
        if event.topic_id:
            span.set_attribute("article.topic_id", str(event.topic_id))

        result = self._use_case.execute(
            analysis_id=event.analysis_id,
            article_id=event.article_id,
            tag_groups=list(event.tag_groups),
            topic_id=event.topic_id,
        )

        span.set_attribute("normalization.success", result.success)
        if result.success:
            logger.info(
                "tag_normalization_completed",
                analysis_id=str(event.analysis_id),
                article_id=str(event.article_id),
            )
            article_title, article_content = self._fetch_article_body(event.article_id)
            self._event_bus.publish(TagNormalizationCompletedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
                article_title=article_title,
                article_content=article_content,
                topic_id=event.topic_id,
            ))
        else:
            if result.exception_type:
                span.set_attribute("normalization.error_type", result.exception_type)
            self._event_bus.publish(TagNormalizationFailedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
                exception_type=result.exception_type,
                exception_message=result.exception_message,
                traceback=result.traceback,
            ))

    def _fetch_article_body(self, article_id) -> tuple[str, str]:
        """Fetch article title and content from the database."""
        try:
            from models.article import Article
            row = self._session.query(Article).filter_by(id=article_id).first()
            if row:
                return row.title or "", row.content or ""
        except Exception as e:
            logger.warning("article_body_fetch_failed", article_id=str(article_id), error=str(e))
        return "", ""
