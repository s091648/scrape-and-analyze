from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.search.application.use_cases.rebuild_search_index_use_case import RebuildSearchIndexUseCase
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SearchIndexRebuildHandler:
    """Rebuilds the autocomplete term index once per completed scrape pipeline run
    (FR-008) — mirrors CacheInvalidationHandler/CacheWarmupHandler's PipelineCompletedEvent
    subscription pattern."""

    def __init__(self, use_case: RebuildSearchIndexUseCase) -> None:
        self._use_case = use_case

    def handle(self, event: PipelineCompletedEvent) -> None:
        logger.info("search_index_rebuild_started")
        try:
            stats = self._use_case.execute()
            logger.info("search_index_rebuild_completed", **stats)
        except Exception:
            logger.exception("search_index_rebuild_failed")
