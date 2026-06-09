from collections import defaultdict
from typing import Any, Callable, Dict, List, Type

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