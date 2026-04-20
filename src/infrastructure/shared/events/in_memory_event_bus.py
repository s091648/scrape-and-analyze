from collections import defaultdict
from typing import Any, Callable, Dict, List, Type

from src.shared.logging import get_logger

logger = get_logger(__name__)


class InMemoryEventBus:
    def __init__(self) -> None:
        self._handlers: Dict[Type, List[Callable]] = defaultdict(list)

    def subscribe(self, event_type: Type[Any], handler: Callable[[Any], None]) -> None:
        self._handlers[event_type].append(handler)
        logger.info("event_handler_registered",
                    event=event_type.__name__,
                    handler=handler.__qualname__)

    def publish(self, event: Any) -> None:
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.warning("event_no_handlers", event=type(event).__name__)
            return
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("event_handler_failed",
                             event=type(event).__name__,
                             handler=handler.__qualname__,
                             error=str(e))
