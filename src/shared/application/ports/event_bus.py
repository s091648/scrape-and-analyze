from typing import Awaitable, Callable, Protocol, Type, Any


class EventBus(Protocol):
    """Protocol for a publish-subscribe event bus used to decouple pipeline stages.

    024-async-pipeline-refactor: async so multiple publish() calls (one per
    concurrently-running article task) can be in flight at once. Handlers for
    the SAME event are still awaited strictly in subscribe()-call order within
    one publish() call — never asyncio.gather'd across sibling handlers — since
    at least one existing handler pair depends on that ordering for correctness,
    not just presentation (see AsyncInMemoryEventBus and
    specs/024-async-pipeline-refactor/contracts/event-bus-port.md).

    This Protocol change does not affect any other pipeline builder
    (build_weekly_pipeline, build_metrics_refresh_pipeline,
    build_dedup_reconciliation_pipeline, build_rag_backfill_pipeline) — each
    owns its own separate, still-synchronous InMemoryEventBus instance and
    never calls through this Protocol type (Python's structural typing isn't
    runtime-enforced), so none of them are affected by this signature change.
    """

    async def subscribe(self, event_type: Type[Any], handler: Callable[[Any], Awaitable[None]]) -> None:
        """Register a handler coroutine function for a given event type."""
        ...

    async def publish(self, event: Any) -> bool:
        """Await all handlers subscribed to type(event), in subscribe()-call
        order; return True if any handler ran."""
        ...