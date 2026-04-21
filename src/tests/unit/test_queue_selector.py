import queue


def _make_queue(*items):
    q = queue.Queue()
    for item in items:
        q.put(item)
    return q


# ── RoundRobinQueueSelector ────────────────────────────────────────────────

def test_round_robin_excludes_empty_queues():
    from src.infrastructure.collection.executor.queue_selector import RoundRobinQueueSelector
    queues = [queue.Queue(), _make_queue("x")]
    sel = RoundRobinQueueSelector()
    candidates = sel.select(queues)
    assert 1 in candidates
    assert 0 not in candidates


def test_round_robin_returns_empty_list_when_all_empty():
    from src.infrastructure.collection.executor.queue_selector import RoundRobinQueueSelector
    queues = [queue.Queue(), queue.Queue()]
    assert RoundRobinQueueSelector().select(queues) == []


def test_round_robin_includes_all_non_empty_queues():
    from src.infrastructure.collection.executor.queue_selector import RoundRobinQueueSelector
    queues = [_make_queue("a"), _make_queue("b"), queue.Queue()]
    candidates = RoundRobinQueueSelector().select(queues)
    assert set(candidates) == {0, 1}


def test_round_robin_rotates_order_across_calls():
    """Successive calls should start from different positions."""
    from src.infrastructure.collection.executor.queue_selector import RoundRobinQueueSelector
    queues = [_make_queue("a", "b"), _make_queue("c", "d")]
    sel = RoundRobinQueueSelector()
    first_call_lead = sel.select(queues)[0]
    second_call_lead = sel.select(queues)[0]
    assert first_call_lead != second_call_lead


# ── WeightedRoundRobinQueueSelector ───────────────────────────────────────

def test_weighted_puts_largest_queue_first():
    from src.infrastructure.collection.executor.queue_selector import WeightedRoundRobinQueueSelector
    queues = [_make_queue("a"), _make_queue("b", "c", "d")]  # sizes 1 and 3
    candidates = WeightedRoundRobinQueueSelector().select(queues)
    assert candidates[0] == 1   # larger queue is first candidate


def test_weighted_excludes_empty_queues():
    from src.infrastructure.collection.executor.queue_selector import WeightedRoundRobinQueueSelector
    queues = [queue.Queue(), _make_queue("x")]
    candidates = WeightedRoundRobinQueueSelector().select(queues)
    assert candidates == [1]


def test_weighted_returns_empty_list_when_all_empty():
    from src.infrastructure.collection.executor.queue_selector import WeightedRoundRobinQueueSelector
    assert WeightedRoundRobinQueueSelector().select([queue.Queue()]) == []