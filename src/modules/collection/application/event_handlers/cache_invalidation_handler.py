from shared.cache import CacheGateway
from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer

_INVALIDATED_NAMESPACES = ("articles", "graph")


class CacheInvalidationHandler:
    """Bumps the read-cache namespaces affected by a completed scrape pipeline run."""

    def __init__(self, cache_gateway: CacheGateway) -> None:
        self._cache = cache_gateway

    async def handle(self, event) -> None:
        """Invalidate cached article/graph reads so newly-scraped data is visible immediately.

        024-async-pipeline-refactor: now subscribed to TextPipelineCompletedEvent
        (not PipelineCompletedEvent) — cached article/graph reads only depend
        on article/analysis text content, not RAG vectors, so this fires as
        soon as the text stage settles rather than waiting on RAG."""
        with get_tracer().start_as_current_span(SpanName.CACHE_INVALIDATION_HANDLE) as span:
            span.set_attribute("cache.namespaces", list(_INVALIDATED_NAMESPACES))
            for namespace in _INVALIDATED_NAMESPACES:
                self._cache.bump_version(namespace)
