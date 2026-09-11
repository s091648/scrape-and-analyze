import asyncio
import time

import pytest

from src.infrastructure.shared.events.settling_task_group import SettlingTaskGroup


@pytest.mark.asyncio
async def test_dispatch_runs_concurrently_not_sequentially():
    group = SettlingTaskGroup()
    started_at: dict[str, float] = {}
    finished_at: dict[str, float] = {}

    async def slow():
        started_at["A"] = time.monotonic()
        await asyncio.sleep(0.2)
        finished_at["A"] = time.monotonic()

    async def fast():
        started_at["B"] = time.monotonic()
        finished_at["B"] = time.monotonic()

    group.dispatch(slow())
    group.dispatch(fast())

    await group.settle()

    # If dispatch() awaited inline (like EventBus.publish()), B would only
    # start after A finished (>= 0.2s later). Dispatched concurrently, B
    # finishes almost immediately, well before A does.
    assert finished_at["B"] < finished_at["A"]


@pytest.mark.asyncio
async def test_dispatch_does_not_await_inline():
    """dispatch() must return before the coroutine has necessarily finished —
    unlike EventBus.publish(), which fully drains every handler."""
    group = SettlingTaskGroup()
    ran = []

    async def slow():
        await asyncio.sleep(0.1)
        ran.append("done")

    group.dispatch(slow())

    assert ran == []  # not finished yet — dispatch() didn't block for it
    await group.settle()
    assert ran == ["done"]


@pytest.mark.asyncio
async def test_settle_returns_results_in_dispatch_order():
    group = SettlingTaskGroup()

    async def value(v):
        return v

    group.dispatch(value(1))
    group.dispatch(value(2))
    group.dispatch(value(3))

    assert await group.settle() == [1, 2, 3]


@pytest.mark.asyncio
async def test_one_failing_task_never_cancels_siblings():
    """settle() uses return_exceptions=True and never cancels sibling tasks
    on one failure — one article's translation/RAG failing must never take
    down another's (unlike stdlib asyncio.TaskGroup's fail-fast behavior)."""
    group = SettlingTaskGroup()
    sibling_ran = []

    async def failing():
        raise RuntimeError("boom")

    async def sibling():
        await asyncio.sleep(0.05)
        sibling_ran.append("done")
        return "ok"

    group.dispatch(failing())
    group.dispatch(sibling())

    outcomes = await group.settle()

    assert sibling_ran == ["done"]
    assert isinstance(outcomes[0], RuntimeError)
    assert outcomes[1] == "ok"


@pytest.mark.asyncio
async def test_settle_with_nothing_dispatched_returns_empty_list():
    group = SettlingTaskGroup()
    assert await group.settle() == []


@pytest.mark.asyncio
async def test_settle_clears_the_group():
    """A second settle() call with nothing newly dispatched must not re-await
    (or re-return) tasks from a previous settle() batch."""
    group = SettlingTaskGroup()

    async def value():
        return "first-batch"

    group.dispatch(value())
    first = await group.settle()
    second = await group.settle()

    assert first == ["first-batch"]
    assert second == []
