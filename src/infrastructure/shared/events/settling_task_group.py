import asyncio
from typing import Any, Awaitable, List


class SettlingTaskGroup:
    """Fork-join primitive for independent background work.

    dispatch() fires a coroutine as its own detached asyncio.Task and tracks
    it; settle() awaits every tracked task and returns their outcomes,
    clearing the group. Deliberately NOT stdlib asyncio.TaskGroup: that type
    cancels every sibling task the moment one raises and re-raises as an
    ExceptionGroup (fail-fast). Every barrier in CollectionPipeline instead
    wants settle semantics — asyncio.gather(..., return_exceptions=True) — so
    one article's translation (or RAG ingestion) failing never cancels or
    blocks any other article's.

    Not an EventBus (src/shared/application/ports/event_bus.py): dispatch()
    does not await inline and makes no ordering guarantee between dispatched
    tasks — only use it for genuinely independent work. The ordered/awaited
    EventBus Protocol is a different, incompatible contract (see its
    docstring and specs/024-async-pipeline-refactor/contracts/event-bus-port.md)
    — do not substitute one for the other.
    """

    def __init__(self) -> None:
        self._tasks: List[asyncio.Task] = []

    def dispatch(self, coro: Awaitable[Any]) -> asyncio.Task:
        """Fire `coro` as a detached asyncio.Task and track it for settle()."""
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task

    async def settle(self, *, return_exceptions: bool = True) -> List[Any]:
        """Await every tracked task (settle semantics, never cancels siblings
        on one failure) and clear the group. Returns each task's result/
        exception in dispatch order; [] if nothing was dispatched."""
        if not self._tasks:
            return []
        tasks, self._tasks = self._tasks, []
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)
