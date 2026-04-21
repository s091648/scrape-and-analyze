def test_routes_task_to_correct_host_queue():
    from src.pipeline.host_queue_map import HostQueueMap
    from src.pipeline.queue_router import QueueRouter
    from src.pipeline.task import ScrapeTask

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    task = ScrapeTask(url="http://arxiv.org/abs/1", source="arxiv",
                      _execute_fn=lambda: None)
    router.route([task])

    idx = hqm.host_map["arxiv.org"]
    assert hqm.queues[idx].qsize() == 1


def test_same_host_tasks_share_one_queue():
    from src.pipeline.host_queue_map import HostQueueMap
    from src.pipeline.queue_router import QueueRouter
    from src.pipeline.task import ScrapeTask

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    tasks = [
        ScrapeTask(url="http://arxiv.org/abs/1", source="arxiv", _execute_fn=lambda: None),
        ScrapeTask(url="http://arxiv.org/abs/2", source="arxiv", _execute_fn=lambda: None),
    ]
    router.route(tasks)
    assert len(hqm.queues) == 1
    assert hqm.queues[0].qsize() == 2


def test_different_hosts_get_separate_queues():
    from src.pipeline.host_queue_map import HostQueueMap
    from src.pipeline.queue_router import QueueRouter
    from src.pipeline.task import ScrapeTask

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    tasks = [
        ScrapeTask(url="http://arxiv.org/abs/1", source="arxiv", _execute_fn=lambda: None),
        ScrapeTask(url="http://example.com/post", source="blog", _execute_fn=lambda: None),
    ]
    router.route(tasks)
    assert len(hqm.queues) == 2


def test_invalid_url_falls_back_to_raw_string_as_host():
    from src.pipeline.host_queue_map import HostQueueMap
    from src.pipeline.queue_router import QueueRouter
    from src.pipeline.task import ScrapeTask

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    task = ScrapeTask(url="not-a-url", source="test", _execute_fn=lambda: None)
    router.route([task])  # must not raise
    assert len(hqm.queues) == 1