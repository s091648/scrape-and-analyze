import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, List, Type

from src.shared.logging import get_logger

logger = get_logger(__name__)


class InMemoryEventBus:
    """Synchronous in-process event bus that dispatches published events to registered handlers."""
    def __init__(self) -> None:
        self._handlers: Dict[Type, List[Callable]] = defaultdict(list)

    def subscribe(self, event_type: Type[Any], handler: Callable[[Any], None]) -> None:
        """Register a handler function to be called when events of the given type are published."""
        self._handlers[event_type].append(handler)
        logger.info("event_handler_registered",
                    event_type=event_type.__name__,
                    handler=handler.__qualname__)

    def publish(self, event: Any) -> bool:
        """Dispatch the event to all registered handlers; returns False if any handler failed."""
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.warning("event_no_handlers", event_type=type(event).__name__)
            return True
        all_ok = True
        for handler in handlers:
            try:
                result = handler(event)
                if result is False:
                    all_ok = False
            except Exception as e:
                logger.error("event_handler_failed",
                             event_type=type(event).__name__,
                             handler=handler.__qualname__,
                             error=str(e))
                all_ok = False
        return all_ok


class AsyncInMemoryEventBus:
    """Async in-process event bus — new sibling of InMemoryEventBus, not a
    replacement (InMemoryEventBus stays untouched; every other pipeline
    builder still constructs and owns its own sync instance of it).

    Only used by build_collection_pipeline(). Concurrency comes from many
    publish() calls (one per concurrently-running article asyncio.Task) being
    in flight at once — NOT from parallelizing handlers within one publish()
    call. Handlers for the same event type are always awaited strictly in
    subscribe()-call order: at least one existing handler pair
    (CacheInvalidationHandler -> CacheWarmupHandler on PipelineCompletedEvent)
    depends on that ordering for correctness (it writes into the cache
    namespace invalidation just bumped to), not merely for how the admin
    monitoring waterfall renders. See
    specs/024-async-pipeline-refactor/contracts/event-bus-port.md.
    """
    def __init__(self) -> None:
        self._handlers: Dict[Type, List[Callable[[Any], Awaitable[None]]]] = defaultdict(list)

    async def subscribe(self, event_type: Type[Any], handler: Callable[[Any], Awaitable[None]]) -> None:
        """Register a handler coroutine function to be awaited (in this order) when events of the given type are published."""
        self._handlers[event_type].append(handler)
        logger.info("async_event_handler_registered",
                    event_type=event_type.__name__,
                    handler=getattr(handler, "__qualname__", repr(handler)))

    async def publish(self, event: Any) -> bool:
        """Await each handler registered for type(event), one at a time, in
        subscribe()-call order; returns False if any handler failed."""
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.warning("event_no_handlers", event_type=type(event).__name__)
            return True
        all_ok = True
        for handler in handlers:
            try:
                result = await handler(event)
                if result is False:
                    all_ok = False
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("event_handler_failed",
                             event_type=type(event).__name__,
                             handler=getattr(handler, "__qualname__", repr(handler)),
                             error=str(e))
                all_ok = False
        return all_ok