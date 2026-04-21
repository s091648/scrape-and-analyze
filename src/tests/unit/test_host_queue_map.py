def test_same_host_returns_same_index():
    from src.pipeline.host_queue_map import HostQueueMap
    m = HostQueueMap()
    assert m.get_or_create("arxiv.org") == m.get_or_create("arxiv.org")


def test_different_hosts_get_different_indices():
    from src.pipeline.host_queue_map import HostQueueMap
    m = HostQueueMap()
    assert m.get_or_create("arxiv.org") != m.get_or_create("example.com")


def test_queues_and_semaphores_count_match_unique_hosts():
    from src.pipeline.host_queue_map import HostQueueMap
    m = HostQueueMap()
    m.get_or_create("arxiv.org")
    m.get_or_create("example.com")
    m.get_or_create("arxiv.org")  # duplicate
    assert len(m.queues) == 2
    assert len(m.semaphores) == 2


def test_semaphore_is_bounded_1():
    """Each queue gets a BoundedSemaphore(1) — acquire twice should fail."""
    from src.pipeline.host_queue_map import HostQueueMap
    m = HostQueueMap()
    idx = m.get_or_create("arxiv.org")
    sem = m.semaphores[idx]
    assert sem.acquire(blocking=False) is True   # first acquire succeeds
    assert sem.acquire(blocking=False) is False  # second acquire fails (value=1)
    sem.release()


def test_put_and_get_task_from_queue():
    from src.pipeline.host_queue_map import HostQueueMap
    from src.pipeline.task import ScrapeTask
    m = HostQueueMap()
    idx = m.get_or_create("arxiv.org")
    task = ScrapeTask(url="http://arxiv.org/abs/1", source="arxiv",
                      _execute_fn=lambda: None)
    m.queues[idx].put(task)
    assert m.queues[idx].get_nowait() is task