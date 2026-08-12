from shared.cache import CacheGateway
from src.modules.collection.application.events import PipelineCompletedEvent


class CacheWarmupHandler:
    """Signals backend's cache-warmup listener to re-populate the default (no-customization)
    reads right after CacheInvalidationHandler bumps their namespace versions, so the first
    visitor after a scrape run doesn't pay a cache-miss cost — only user-customized filter
    combinations remain lazily populated via cache-aside (research.md decision, 020-redis-
    caching-layer).

    Must run strictly after CacheInvalidationHandler.bump_version() for the same event, or the
    warmed entries would land under a namespace version that's about to be orphaned — bootstrap.py
    subscribes this handler second to guarantee that ordering (InMemoryEventBus dispatches
    subscribers in subscribe()-call order).

    Publishes a Redis Pub/Sub signal (CacheGateway.publish_warmup_signal()) instead of making
    HTTP calls to backend's own endpoints — the earlier HTTP self-call design gave src/ a
    runtime dependency on backend being reachable over the network for no benefit beyond code
    reuse, which backend's own listener now gets for free by calling its own service functions
    directly (see backend/cache_warmup.py). A missed/lost signal (Redis Pub/Sub has no
    persistence) only costs one extra cache miss for the next visitor — never a correctness
    issue, since bump_version() has already made the old entries unreachable.
    """

    def __init__(self, cache_gateway: CacheGateway) -> None:
        self._cache = cache_gateway

    def handle(self, event: PipelineCompletedEvent) -> None:
        self._cache.publish_warmup_signal(reason="scraper_pipeline")
