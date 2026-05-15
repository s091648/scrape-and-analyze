def test_routes_task_to_correct_host_queue():
    from src.infrastructure.collection.executor.host_queue_map import HostQueueMap
    from src.infrastructure.collection.executor.queue_router import QueueRouter
    from src.infrastructure.collection.executor.fetch_task import FetchTask
    from src.modules.collection.domain.entities import ScrapeJob
    from unittest.mock import MagicMock

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    job = ScrapeJob(url="http://arxiv.org/abs/1", source="arxiv", source_type="arxiv")
    task = FetchTask(url="http://arxiv.org/abs/1", source="arxiv",
                     job=job, scraper=MagicMock())
    router.route([task])

    idx = hqm.host_map["arxiv.org"]
    assert hqm.queues[idx].qsize() == 1


def test_same_host_tasks_share_one_queue():
    from src.infrastructure.collection.executor.host_queue_map import HostQueueMap
    from src.infrastructure.collection.executor.queue_router import QueueRouter
    from src.infrastructure.collection.executor.fetch_task import FetchTask
    from src.modules.collection.domain.entities import ScrapeJob
    from unittest.mock import MagicMock

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    job1 = ScrapeJob(url="http://arxiv.org/abs/1", source="arxiv", source_type="arxiv")
    job2 = ScrapeJob(url="http://arxiv.org/abs/2", source="arxiv", source_type="arxiv")
    router.route([
        FetchTask(url="http://arxiv.org/abs/1", source="arxiv", job=job1, scraper=MagicMock()),
        FetchTask(url="http://arxiv.org/abs/2", source="arxiv", job=job2, scraper=MagicMock()),
    ])
    assert len(hqm.queues) == 1
    assert hqm.queues[0].qsize() == 2


def test_routes_discover_task_to_correct_host_queue():
    from src.infrastructure.collection.executor.host_queue_map import HostQueueMap
    from src.infrastructure.collection.executor.queue_router import QueueRouter
    from src.infrastructure.collection.executor.discover_task import DiscoverTask
    from unittest.mock import MagicMock

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    setting = MagicMock()
    scraper = MagicMock()
    task = DiscoverTask(setting=setting, scraper=scraper, host="export.arxiv.org")

    router.route_discover([task])

    idx = hqm.host_map["export.arxiv.org"]
    assert hqm.queues[idx].qsize() == 1