from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer
from src.modules.search.application.use_cases.rebuild_search_index_use_case import RebuildSearchIndexUseCase
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SearchIndexRebuildHandler:
    """Rebuilds the autocomplete term index once per completed scrape pipeline run
    (FR-008) — mirrors CacheInvalidationHandler/CacheWarmupHandler's subscription
    pattern.

    024-async-pipeline-refactor: now subscribed to TextPipelineCompletedEvent
    (not PipelineCompletedEvent) — the index only depends on article/analysis
    text content, not RAG vectors. `handle()` is `async def` for the EventBus
    Protocol, but RebuildSearchIndexUseCase.execute() itself stays a plain
    synchronous bulk query (SearchTermRepository is intentionally not async —
    see contracts/async-repository-ports.md — this is a once-per-run bulk
    operation, not part of the per-article concurrent path)."""

    def __init__(self, use_case: RebuildSearchIndexUseCase) -> None:
        self._use_case = use_case

    async def handle(self, event) -> None:
        with get_tracer().start_as_current_span(SpanName.SEARCH_INDEX_REBUILD_HANDLE) as span:
            logger.info("search_index_rebuild_started")
            try:
                stats = self._use_case.execute()
                span.set_attribute("search_index.article_count", stats["article_count"])
                span.set_attribute("search_index.topic_count", stats["topic_count"])
                span.set_attribute("search_index.term_count", stats["term_count"])
                logger.info("search_index_rebuild_completed", **stats)
            except Exception:
                logger.exception("search_index_rebuild_failed")
