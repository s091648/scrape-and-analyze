from typing import Callable, Protocol, Type, Any


class EventBus(Protocol):
    """Protocol for a publish-subscribe event bus used to decouple pipeline stages."""

    def subscribe(self, event_type: Type[Any], handler: Callable[[Any], None]) -> None:
        """Register a handler callable for a given event type."""
        ...

    def publish(self, event: Any) -> bool:
        """Dispatch an event to all subscribed handlers; returns True if any handler ran."""
        ...