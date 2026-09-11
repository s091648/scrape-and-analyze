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

    fix/sanitize: no longer fetches the article body (title/content) — that
    was only ever done as a courtesy relay for translation, which used to
    chain off TagNormalizationCompletedEvent to receive those fields.
    Translation now fans out independently off AnalysisCompletedEvent and
    fetches its own article body (AnalysisCompletedHandler), so a transient
    DB read failure here can no longer be mislabeled as "tag normalization
    failed" (and can no longer block translation either) when tag
    normalization itself actually succeeded.
    """

    def __init__(self, use_case: NormalizeTagsUseCase, event_bus, session=None) -> None:
        self._use_case = use_case
        self._event_bus = event_bus
        # session kept for backwards-compatible construction — no longer used
        # by this handler itself (see class docstring), but bootstrap.py may
        # still pass the per-article session through unchanged.
        self._session = session

    async def handle(self, event: AnalysisCompletedEvent) -> None:
        """Run tag normalization on the analysis result and publish outcome.

        024-async-pipeline-refactor follow-up: owns its own span (see
        ArticleScrapedHandler.handle's docstring for why).
        """
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
                next_event = TagNormalizationCompletedEvent(
                    analysis_id=event.analysis_id,
                    article_id=event.article_id,
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
