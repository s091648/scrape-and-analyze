def test_same_host_returns_same_index():
    from src.infrastructure.collection.executor.host_queue_map import HostQueueMap
    m = HostQueueMap()
    assert m.get_or_create("arxiv.org") == m.get_or_create("arxiv.org")


def test_different_hosts_get_different_indices():
    from src.infrastructure.collection.executor.host_queue_map import HostQueueMap
    m = HostQueueMap()
    assert m.get_or_create("arxiv.org") != m.get_or_create("example.com")


def test_queues_and_semaphores_count_match_unique_hosts():
    from src.infrastructure.collection.executor.host_queue_map import HostQueueMap
    m = HostQueueMap()
    m.get_or_create("arxiv.org")
    m.get_or_create("example.com")
    m.get_or_create("arxiv.org")
    assert len(m.queues) == 2
    assert len(m.semaphores) == 2