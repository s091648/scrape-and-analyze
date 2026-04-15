from typing import Protocol, Callable, Any

class EventBus(Protocol):
    def subscribe(self, event_type: str, handler: Callable) -> None:
        ...

    def publish(self, event: Any) -> None:
        ...