"""US5 (024-async-pipeline-refactor) T063: a minimal stub EventBus Protocol
implementation — an in-memory call recorder with no real dispatch logic.

Exists to prove the pipeline's stage-handoff mechanism depends only on the
abstract EventBus Protocol (src/shared/application/ports/event_bus.py), never
a concrete implementation — a future Redis Streams-backed EventBus would be a
drop-in swap requiring no changes to any handler/use-case code. This stub is
deliberately NOT a working pub/sub bus (subscribe() just records calls;
publish() just records calls and does nothing else) since T064 only needs to
confirm build_collection_pipeline() *constructs* successfully with it swapped
in, not that a full pipeline run behaves correctly against it.
"""
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Tuple, Type


@dataclass
class StubEventBus:
    """Records every subscribe()/publish() call it receives; dispatches nothing."""

    subscriptions: List[Tuple[Type[Any], Callable[[Any], Awaitable[None]]]] = field(default_factory=list)
    published: List[Any] = field(default_factory=list)

    async def subscribe(self, event_type: Type[Any], handler: Callable[[Any], Awaitable[None]]) -> None:
        self.subscriptions.append((event_type, handler))

    async def publish(self, event: Any) -> bool:
        self.published.append(event)
        return False
