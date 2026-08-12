from shared.cache import CacheGateway
from src.modules.collection.application.events import PipelineCompletedEvent

_INVALIDATED_NAMESPACES = ("articles", "graph")


class CacheInvalidationHandler:
    """Bumps the read-cache namespaces affected by a completed scrape pipeline run."""

    def __init__(self, cache_gateway: CacheGateway) -> None:
        self._cache = cache_gateway

    def handle(self, event: PipelineCompletedEvent) -> None:
        """Invalidate cached article/graph reads so newly-scraped data is visible immediately."""
        for namespace in _INVALIDATED_NAMESPACES:
            self._cache.bump_version(namespace)
