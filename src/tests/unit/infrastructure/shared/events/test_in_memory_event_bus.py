import asyncio
import time

import pytest

from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus


class _EventA:
    pass


class _EventB:
    pass


@pytest.mark.asyncio
async def test_publish_awaits_handlers_for_same_event_in_subscribe_order():
    bus = AsyncInMemoryEventBus()
    call_order: list[str] = []

    async def handler_one(event):
        call_order.append("one")

    async def handler_two(event):
        call_order.append("two")

    await bus.subscribe(_EventA, handler_one)
    await bus.subscribe(_EventA, handler_two)

    await bus.publish(_EventA())

    assert call_order == ["one", "two"]


@pytest.mark.asyncio
async def test_handler_exception_does_not_prevent_sibling_handlers_from_running():
    bus = AsyncInMemoryEventBus()
    call_order: list[str] = []

    async def failing_handler(event):
        call_order.append("failing")
        raise RuntimeError("boom")

    async def sibling_handler(event):
        call_order.append("sibling")

    await bus.subscribe(_EventA, failing_handler)
    await bus.subscribe(_EventA, sibling_handler)

    result = await bus.publish(_EventA())

    assert call_order == ["failing", "sibling"]
    assert result is False


@pytest.mark.asyncio
async def test_publish_calls_for_different_events_run_concurrently():
    bus = AsyncInMemoryEventBus()
    started_at: dict[str, float] = {}
    finished_at: dict[str, float] = {}

    async def slow_handler(event):
        started_at["A"] = time.monotonic()
        await asyncio.sleep(0.2)
        finished_at["A"] = time.monotonic()

    async def fast_handler(event):
        started_at["B"] = time.monotonic()
        finished_at["B"] = time.monotonic()

    await bus.subscribe(_EventA, slow_handler)
    await bus.subscribe(_EventB, fast_handler)

    await asyncio.gather(bus.publish(_EventA()), bus.publish(_EventB()))

    # If the two publish() calls ran sequentially, B's handler would only
    # start after A's slow handler fully finished (>= 0.2s later). Running
    # concurrently, B finishes almost immediately, well before A does.
    assert finished_at["B"] < finished_at["A"]


@pytest.mark.asyncio
async def test_publish_returns_true_when_a_handler_ran():
    bus = AsyncInMemoryEventBus()

    async def handler(event):
        return None

    await bus.subscribe(_EventA, handler)

    assert await bus.publish(_EventA()) is True


@pytest.mark.asyncio
async def test_publish_returns_true_with_no_subscribers():
    bus = AsyncInMemoryEventBus()

    assert await bus.publish(_EventA()) is True
