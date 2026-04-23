from typing import Callable, Protocol, Type, Any


class EventBus(Protocol):
    def subscribe(self, event_type: Type[Any], handler: Callable[[Any], None]) -> None:
        ...

    def publish(self, event: Any) -> bool:
        ...