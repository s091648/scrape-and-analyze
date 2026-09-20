from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer
from src.modules.intelligence.application.use_cases.refresh_tag_article_counts_use_case import (
    RefreshTagArticleCountsUseCase,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class TagCountsRefreshHandler:
    """Refreshes intelligence.tag_article_counts once per completed scrape pipeline
    run — mirrors SearchIndexRebuildHandler's subscription to the same
    TextPipelineCompletedEvent (both are read models derived from article/tag text
    content, not RAG vectors). `handle()` is `async def` for the EventBus Protocol;
    RefreshTagArticleCountsUseCase.execute() itself stays a plain synchronous
    REFRESH MATERIALIZED VIEW CONCURRENTLY statement — a once-per-run operation,
    not part of the per-article concurrent path."""

    def __init__(self, use_case: RefreshTagArticleCountsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, event) -> None:
        with get_tracer().start_as_current_span(SpanName.TAG_COUNTS_REFRESH_HANDLE):
            logger.info("tag_counts_refresh_started")
            try:
                self._use_case.execute()
            except Exception:
                logger.exception("tag_counts_refresh_failed")
