from abc import ABC, abstractmethod
from typing import List


class ProviderSelector(ABC):
    """024-async-pipeline-refactor: strategy interface for ordering provider/
    embedding-provider handlers for a concurrent dispatch attempt — mirrors
    QueueSelector (src/infrastructure/collection/executor/queue_selector.py),
    applied to LLM/embedding provider dispatch instead of host queues. See
    contracts/provider-selector-port.md for the full behavioral contract.

    select() itself is side-effect-free — it only inspects each handler's
    `strategy.has_capacity(estimated_tokens)` and returns an ordering; it
    never reserves capacity. Reservation happens when the caller goes
    straight from this ordering into `await handler.analyze(...)`, whose
    first line calls `strategy.try_acquire()` with that same estimate —
    synchronously, on the event loop thread, so it stays atomic with this
    call with no other concurrently-gathered task able to interleave. See
    AsyncResilientLLMService.analyze/translate/generate and
    AsyncProviderHandler's docstring for the non-blocking-first/thread-hop-
    fallback split and why it closes the race an earlier, always-thread-
    offloaded design had.
    """

    @abstractmethod
    def select(self, handlers: List, estimated_tokens: int = 0) -> List[int]:
        """Return indices of currently-available handlers, in preferred
        dispatch order, for a request estimated at `estimated_tokens`.
        Returns [] if none are currently available (caller falls back to the
        existing blocking-equivalent wait, in original priority order, on
        the whole handler list). `estimated_tokens` must be the same
        estimate the caller will use for reservation — a handler that's
        only "available" for a 0-token request can still be TPM-full for
        the request actually being dispatched."""


class PriorityFirstProviderSelector(ProviderSelector):
    """Default. Preserves today's priority ordering among handlers that
    currently have capacity — does not change *which* model is preferred,
    only skips ones that are momentarily unavailable instead of blocking on
    them (FR-010). Handlers are assumed pre-sorted by priority (as
    AsyncResilientLLMService/AsyncResilientEmbeddingService already keep
    `self._handlers`), so this only needs to filter, not sort."""

    def select(self, handlers: List, estimated_tokens: int = 0) -> List[int]:
        """Return indices of handlers with current capacity for
        `estimated_tokens`, preserving `handlers`' existing (priority)
        order."""
        return [i for i, h in enumerate(handlers) if h.strategy.has_capacity(estimated_tokens)]
