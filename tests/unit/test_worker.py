import threading
import queue
from unittest.mock import patch


def _make_article(n=0):
    from src.scrapers.scrapers.article import ScrapedArticle
    return ScrapedArticle(url=f"http://x.com/{n}", title=f"T{n}",
                          content="C", published_at=None, source="test")


def _make_task(article=None):
    from src.scrapers.strategy.scrape_task import ScrapeTask
    return ScrapeTask(url="http://example.com/a", source="test",
                      _execute_fn=lambda: article)


def _run_workers(tasks_by_host, num_workers=1, delay=0.0):
    """Build infrastructure, run workers, return collected results."""
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    from src.scrapers.strategy.queue_selector import WeightedRoundRobinQueueSelector
    from src.scrapers.strategy.worker import ScraperWorker

    hqm = HostQueueMap()
    for host, tasks in tasks_by_host.items():
        idx = hqm.get_or_create(host)
        for t in tasks:
            hqm.queues[idx].put(t)

    done_event = threading.Event()
    selector = WeightedRoundRobinQueueSelector()
    results = []

    workers = [
        ScraperWorker(
            worker_id=i,
            host_queue_map=hqm,
            selector=selector,
            done_event=done_event,
            on_result=results.append,
            delay=delay,
        )
        for i in range(num_workers)
    ]
    for w in workers:
        w.start()
    done_event.set()
    for w in workers:
        w.join()
    return results


def test_worker_executes_task_and_delivers_result():
    article = _make_article()
    results = _run_workers({"example.com": [_make_task(article)]})
    assert results == [article]


def test_worker_skips_none_result():
    results = _run_workers({"example.com": [_make_task(None)]})
    assert results == []


def test_worker_processes_multiple_tasks():
    articles = [_make_article(i) for i in range(4)]
    tasks = [_make_task(a) for a in articles]
    results = _run_workers({"example.com": tasks})
    assert len(results) == 4


def test_worker_terminates_with_no_tasks():
    results = _run_workers({})
    assert results == []


def test_two_workers_never_concurrently_process_same_host():
    """
    Both workers target the same host queue.
    BoundedSemaphore(1) must ensure at most one runs at a time.
    Detect violations by checking overlap in execution windows.
    """
    import time
    windows = []
    lock = threading.Lock()

    def slow_fn():
        start = time.monotonic()
        time.sleep(0.05)
        end = time.monotonic()
        with lock:
            windows.append((start, end))
        return _make_article()

    from src.scrapers.strategy.scrape_task import ScrapeTask
    tasks = [
        ScrapeTask(url="http://example.com/a", source="test", _execute_fn=slow_fn),
        ScrapeTask(url="http://example.com/b", source="test", _execute_fn=slow_fn),
    ]

    with patch("src.pipeline.worker.time.sleep"):
        results = _run_workers({"example.com": tasks}, num_workers=2)

    assert len(results) == 2
    # Windows must not overlap — second starts after first ends
    windows.sort()
    assert windows[1][0] >= windows[0][1], "Concurrent access to same host detected!"


def test_worker_sleeps_between_tasks():
    tasks = [_make_task(_make_article(i)) for i in range(2)]
    with patch("src.pipeline.worker.time.sleep") as mock_sleep:
        _run_workers({"example.com": tasks}, delay=5.0)
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    # Sentry SDK background threads may call time.sleep with unrelated values;
    # assert exactly 2 worker delay calls with the configured value.
    assert sleep_calls.count(5.0) == 2