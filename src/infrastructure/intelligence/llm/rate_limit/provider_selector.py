from abc import ABC, abstractmethod
from typing import List


class ProviderSelector(ABC):
    """024-async-pipeline-refactor: strategy interface for ordering provider/
    embedding-provider handlers for a concurrent dispatch attempt — mirrors
    QueueSelector (src/infrastructure/collection/executor/queue_selector.py),
    applied to LLM/embedding provider dispatch instead of host queues. See
    contracts/provider-selector-port.md for the full behavioral contract.

    select() itself is side-effect-free — it only inspects each handler's
    `strategy.has_capacity()` and returns an ordering; it never reserves
    capacity. Reservation happens naturally when the caller goes straight
    from this ordering into `await handler.analyze(...)` (whose first line
    calls `strategy.acquire()`) with no `await` in between — see
    AsyncResilientLLMService.analyze/translate/generate.
    """

    @abstractmethod
    def select(self, handlers: List) -> List[int]:
        """Return indices of currently-available handlers, in preferred
        dispatch order. Returns [] if none are currently available (caller
        falls back to the existing blocking-equivalent wait, in original
        priority order, on the whole handler list)."""


class PriorityFirstProviderSelector(ProviderSelector):
    """Default. Preserves today's priority ordering among handlers that
    currently have capacity — does not change *which* model is preferred,
    only skips ones that are momentarily unavailable instead of blocking on
    them (FR-010). Handlers are assumed pre-sorted by priority (as
    AsyncResilientLLMService/AsyncResilientEmbeddingService already keep
    `self._handlers`), so this only needs to filter, not sort."""

    def select(self, handlers: List) -> List[int]:
        """Return indices of handlers with current capacity, preserving
        `handlers`' existing (priority) order."""
        return [i for i, h in enumerate(handlers) if h.strategy.has_capacity()]
