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


def test_get_or_create_is_thread_safe():
    """Concurrent calls to get_or_create for the same host must not duplicate entries."""
    import threading
    from src.infrastructure.collection.executor.host_queue_map import HostQueueMap

    m = HostQueueMap()
    errors = []

    def worker(host):
        try:
            m.get_or_create(host)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=("arxiv.org",)) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(m.queues) == 1
    assert len(m.semaphores) == 1