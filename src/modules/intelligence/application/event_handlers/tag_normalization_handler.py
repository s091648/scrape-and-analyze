from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer
from src.shared.logging import get_logger
from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    TagNormalizationCompletedEvent,
    TagNormalizationFailedEvent,
)
from src.modules.intelligence.application.use_cases import NormalizeTagsUseCase

logger = get_logger(__name__)


class TagNormalizationHandler:
    """Normalizes tags from a completed analysis and emits the result event.

    024-async-pipeline-refactor: converted to async in place — confirmed
    constructed only once, only inside build_collection_pipeline(). Takes the
    per-article-task's own AsyncSession now (never shared across concurrently
    running article tasks).
    """

    def __init__(self, use_case: NormalizeTagsUseCase, event_bus, session: AsyncSession) -> None:
        self._use_case = use_case
        self._event_bus = event_bus
        self._session = session

    async def handle(self, event: AnalysisCompletedEvent) -> None:
        """Run tag normalization on the analysis result and publish outcome.

        024-async-pipeline-refactor follow-up: owns its own span (see
        ArticleScrapedHandler.handle's docstring for why). Exactly one
        follow-up event is always published, after the span closes, so it's
        a sibling under article.pipeline rather than nested inside
        article.tag_normalization.handle.
        """
        next_event = None
        with get_tracer().start_as_current_span(SpanName.TAG_NORMALIZATION_HANDLE) as span:
            span.set_attribute("analysis.id", str(event.analysis_id))
            span.set_attribute("article.id", str(event.article_id))
            span.set_attribute("tags.group_count", len(event.tag_groups))
            span.set_attribute("tags.total_count", sum(len(tags) for _, tags in event.tag_groups))
            span.set_attribute("tags.group_names", [g for g, _ in event.tag_groups])
            span.set_attribute("tags.tag_names", [t for _, tags in event.tag_groups for t in tags])
            if event.topic_id:
                span.set_attribute("article.topic_id", str(event.topic_id))

            result = await self._use_case.execute(
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
                try:
                    article_title, article_content = await self._fetch_article_body(event.article_id)
                except Exception as e:
                    logger.error("article_body_fetch_failed", article_id=str(event.article_id), error=str(e))
                    next_event = TagNormalizationFailedEvent(
                        analysis_id=event.analysis_id,
                        article_id=event.article_id,
                        exception_type=type(e).__name__,
                        exception_message=str(e),
                    )
                else:
                    next_event = TagNormalizationCompletedEvent(
                        analysis_id=event.analysis_id,
                        article_id=event.article_id,
                        article_title=article_title,
                        article_content=article_content,
                        topic_id=event.topic_id,
                    )
            else:
                if result.exception_type:
                    span.set_attribute("normalization.error_type", result.exception_type)
                next_event = TagNormalizationFailedEvent(
                    analysis_id=event.analysis_id,
                    article_id=event.article_id,
                    exception_type=result.exception_type,
                    exception_message=result.exception_message,
                    traceback=result.traceback,
                )

        await self._event_bus.publish(next_event)

    async def _fetch_article_body(self, article_id) -> tuple[str, str]:
        """Fetch article title and content from the database.

        Raises on DB failure so the caller can publish a TagNormalizationFailedEvent.
        """
        from models.article import Article
        result = await self._session.execute(select(Article).filter_by(id=article_id))
        row = result.scalars().first()
        if row:
            return row.title or "", row.content or ""
        return "", ""
