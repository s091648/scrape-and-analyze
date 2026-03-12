# Scraper Queue Strategy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor scrapers to use a per-host queue strategy with single-threaded access per host (enforced via `BoundedSemaphore(1)`) and 5-second inter-request delay, and fix ArxivScraper to enable PDF fetching by default.

**Architecture:** Scrapers split into `discover()` (enumerate tasks) and per-task `execute()` closures. `ScrapeDispatcher` routes tasks into per-host queues via `QueueRouter`, then a fixed worker pool processes tasks using a pluggable `QueueSelector` (default: `WeightedRoundRobinQueueSelector`). Each host queue has a `BoundedSemaphore(1)` — workers acquire it non-blockingly to enforce single-thread-per-host without any shared lock or `busy_indices` set.

**Tech Stack:** Python 3.11, `threading.BoundedSemaphore`, `queue.Queue`, requests, feedparser, beautifulsoup4, PyMuPDF (fitz), pytest, responses (mock HTTP)

---

## Chunk 1: Foundation — ScrapedArticle, ScrapeTask, BaseScraper

### Task 1: Move ScrapedArticle to its own module

**Why:** `ScrapeTask` (in `strategy/`) needs to reference `ScrapedArticle` as a return type. If `ScrapedArticle` stays in `base_scraper.py` and `scrape_task.py` imports it, while `base_scraper.py` later imports `ScrapeTask`, we get a circular import. Extracting `ScrapedArticle` breaks the cycle cleanly.

**Files:**
- Create: `src/scrapers/scrapers/article.py`
- Modify: `src/scrapers/scrapers/base_scraper.py`

- [x] **Step 1: Write the failing test**

```python
# tests/unit/test_article.py
def test_scraped_article_dataclass():
    from src.scrapers.scrapers.article import ScrapedArticle
    a = ScrapedArticle(url="http://x.com", title="T", content="C",
                       published_at="2024-01-01", source="test")
    assert a.url == "http://x.com"
    assert a.metadata == {}
```

- [x] **Step 2: Run to verify it fails**

```
docker compose run --rm app python -m pytest tests/unit/test_article.py -v 2>&1
```
Expected: `ModuleNotFoundError`

- [x] **Step 3: Create `src/scrapers/scrapers/article.py`**

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ScrapedArticle:
    """Data class representing a scraped article."""
    url: str
    title: str
    content: str
    published_at: Optional[str]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
```

- [x] **Step 4: Update `src/scrapers/scrapers/base_scraper.py`** — replace the inline `ScrapedArticle` definition with an import + re-export so existing code that does `from base_scraper import ScrapedArticle` still works:

```python
from abc import ABC, abstractmethod
from typing import List

from src.scrapers.scrapers.article import ScrapedArticle  # re-exported for back-compat

__all__ = ['BaseScraper', 'ScrapedArticle']


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def scrape(self) -> List[ScrapedArticle]:
        """Legacy interface. Replaced by discover() in Task 3."""
        pass
```

- [x] **Step 5: Run scraper tests to verify nothing broke**

```
docker compose run --rm app python -m pytest tests/unit/test_article.py tests/unit/test_arxiv_scraper.py tests/unit/test_blog_scraper.py tests/unit/test_rss_scraper.py -v
```
Expected: all pass

- [x] **Step 6: Commit**

```bash
git add src/scrapers/scrapers/article.py src/scrapers/scrapers/base_scraper.py tests/unit/test_article.py
git commit -m "🏖️ [REFACTOR] extract ScrapedArticle into article.py to prevent future circular import"
```

---

### Task 2: Create ScrapeTask + strategy package

**Files:**
- Create: `src/scrapers/strategy/__init__.py`
- Create: `src/scrapers/strategy/scrape_task.py`
- Create: `tests/unit/test_scrape_task.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_scrape_task.py
def test_execute_calls_fn_and_returns_result():
    from src.scrapers.strategy.scrape_task import ScrapeTask
    from src.scrapers.scrapers.article import ScrapedArticle
    article = ScrapedArticle(url="http://x.com", title="T", content="C",
                             published_at=None, source="test")
    task = ScrapeTask(url="http://x.com", source="test", _execute_fn=lambda: article)
    assert task.execute() is article


def test_execute_returns_none_on_exception():
    from src.scrapers.strategy.scrape_task import ScrapeTask
    task = ScrapeTask(url="http://x.com", source="test",
                      _execute_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert task.execute() is None


def test_task_has_url_and_source():
    from src.scrapers.strategy.scrape_task import ScrapeTask
    task = ScrapeTask(url="http://a.com/p", source="blog", _execute_fn=lambda: None)
    assert task.url == "http://a.com/p"
    assert task.source == "blog"
    assert task.metadata == {}
```

- [ ] **Step 2: Run to verify they fail**

```
docker compose run --rm app python -m pytest tests/unit/test_scrape_task.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/scrapers/strategy/__init__.py`** (empty file)

- [ ] **Step 4: Create `src/scrapers/strategy/scrape_task.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapeTask:
    """
    A unit of scrape work routable by host.

    url          — used by QueueRouter to determine the target host.
    source       — human-readable source name (e.g. 'arxiv', 'techcrunch').
    metadata     — optional extra data for logging/debugging.
    _execute_fn  — zero-arg callable injected by the scraper at discover() time.
                   Captures all required state via closure.
    """
    url: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    _execute_fn: Callable[[], Optional[ScrapedArticle]] = field(repr=False)

    def execute(self) -> Optional[ScrapedArticle]:
        """Invoke the injected fetch function. Returns None on any exception."""
        try:
            return self._execute_fn()
        except Exception as e:
            logger.error("scrape_task_execute_failed", url=self.url, error=str(e))
            return None
```

- [ ] **Step 5: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_scrape_task.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/scrapers/strategy/ tests/unit/test_scrape_task.py
git commit -m "⛲ [FEAT] add ScrapeTask with safe execute() and strategy package skeleton"
```

---

### Task 3: Add discover() to BaseScraper

**Files:**
- Modify: `src/scrapers/scrapers/base_scraper.py`

- [ ] **Step 1: Update `base_scraper.py`** — add `discover()` as the new abstract method, keep `scrape()` as a migration bridge that calls `discover()` + `execute()` so existing tests keep passing during the refactor:

```python
from abc import ABC, abstractmethod
from typing import List

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.strategy.scrape_task import ScrapeTask

__all__ = ['BaseScraper', 'ScrapedArticle']


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def discover(self) -> List[ScrapeTask]:
        """
        Phase 1: enumerate all work items for this source.
        Makes the minimum HTTP requests needed to find article URLs
        (e.g. one feed fetch, one listing page fetch).
        Returns [] on any failure.
        """
        pass

    def scrape(self) -> List[ScrapedArticle]:
        """
        Migration bridge: discover + execute all tasks synchronously.
        Kept so existing tests pass while concrete scrapers are being migrated.
        Removed in Task 12 once all scrapers implement discover().
        """
        results = []
        for task in self.discover():
            article = task.execute()
            if article is not None:
                results.append(article)
        return results
```

- [ ] **Step 2: Run existing scraper tests** (scrapers still have their own `scrape()` override — bridge is not reached yet)

```
docker compose run --rm app python -m pytest tests/unit/test_arxiv_scraper.py tests/unit/test_blog_scraper.py tests/unit/test_rss_scraper.py -v
```
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add src/scrapers/scrapers/base_scraper.py
git commit -m "🛞 [FEAT] add discover() abstract method to BaseScraper, keep scrape() as migration bridge"
```

---

## Chunk 2: Queue Infrastructure

### Task 4: HostQueueMap

**Files:**
- Create: `src/scrapers/strategy/host_queue_map.py`
- Create: `tests/unit/test_host_queue_map.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_host_queue_map.py
def test_same_host_returns_same_index():
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    m = HostQueueMap()
    assert m.get_or_create("arxiv.org") == m.get_or_create("arxiv.org")


def test_different_hosts_get_different_indices():
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    m = HostQueueMap()
    assert m.get_or_create("arxiv.org") != m.get_or_create("example.com")


def test_queues_and_semaphores_count_match_unique_hosts():
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    m = HostQueueMap()
    m.get_or_create("arxiv.org")
    m.get_or_create("example.com")
    m.get_or_create("arxiv.org")  # duplicate
    assert len(m.queues) == 2
    assert len(m.semaphores) == 2


def test_semaphore_is_bounded_1():
    """Each queue gets a BoundedSemaphore(1) — acquire twice should fail."""
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    m = HostQueueMap()
    idx = m.get_or_create("arxiv.org")
    sem = m.semaphores[idx]
    assert sem.acquire(blocking=False) is True   # first acquire succeeds
    assert sem.acquire(blocking=False) is False  # second acquire fails (value=1)
    sem.release()


def test_put_and_get_task_from_queue():
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    from src.scrapers.strategy.scrape_task import ScrapeTask
    m = HostQueueMap()
    idx = m.get_or_create("arxiv.org")
    task = ScrapeTask(url="http://arxiv.org/abs/1", source="arxiv",
                      _execute_fn=lambda: None)
    m.queues[idx].put(task)
    assert m.queues[idx].get_nowait() is task
```

- [ ] **Step 2: Run to verify they fail**

```
docker compose run --rm app python -m pytest tests/unit/test_host_queue_map.py -v
```

- [ ] **Step 3: Create `src/scrapers/strategy/host_queue_map.py`**

```python
import threading
from queue import Queue
from typing import Dict, List

from src.scrapers.strategy.scrape_task import ScrapeTask


class HostQueueMap:
    """
    Mapping table: hostname (str) → queue index (int).

    Each host gets:
    - A Queue[ScrapeTask] for pending work.
    - A BoundedSemaphore(1) for single-thread-per-host mutual exclusion.

    Created fresh per scrape job.
    get_or_create() is NOT thread-safe — call only from the single-threaded
    Phase 1 (routing) before workers start.
    """

    def __init__(self) -> None:
        self._map: Dict[str, int] = {}
        self._queues: List[Queue[ScrapeTask]] = []
        self._semaphores: List[threading.BoundedSemaphore] = []

    def get_or_create(self, host: str) -> int:
        """Return existing queue index for host, or allocate a new queue + semaphore."""
        if host not in self._map:
            self._map[host] = len(self._queues)
            self._queues.append(Queue())
            self._semaphores.append(threading.BoundedSemaphore(1))
        return self._map[host]

    @property
    def queues(self) -> List[Queue[ScrapeTask]]:
        return self._queues

    @property
    def semaphores(self) -> List[threading.BoundedSemaphore]:
        return self._semaphores

    @property
    def host_map(self) -> Dict[str, int]:
        return dict(self._map)
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_host_queue_map.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/strategy/host_queue_map.py tests/unit/test_host_queue_map.py
git commit -m "🌚 [FEAT] add HostQueueMap with per-host BoundedSemaphore(1) for mutual exclusion"
```

---

### Task 5: QueueRouter

**Files:**
- Create: `src/scrapers/strategy/queue_router.py`
- Create: `tests/unit/test_queue_router.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_queue_router.py
def test_routes_task_to_correct_host_queue():
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    from src.scrapers.strategy.queue_router import QueueRouter
    from src.scrapers.strategy.scrape_task import ScrapeTask

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    task = ScrapeTask(url="http://arxiv.org/abs/1", source="arxiv",
                      _execute_fn=lambda: None)
    router.route([task])

    idx = hqm.host_map["arxiv.org"]
    assert hqm.queues[idx].qsize() == 1


def test_same_host_tasks_share_one_queue():
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    from src.scrapers.strategy.queue_router import QueueRouter
    from src.scrapers.strategy.scrape_task import ScrapeTask

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
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    from src.scrapers.strategy.queue_router import QueueRouter
    from src.scrapers.strategy.scrape_task import ScrapeTask

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    tasks = [
        ScrapeTask(url="http://arxiv.org/abs/1", source="arxiv", _execute_fn=lambda: None),
        ScrapeTask(url="http://example.com/post", source="blog", _execute_fn=lambda: None),
    ]
    router.route(tasks)
    assert len(hqm.queues) == 2


def test_invalid_url_falls_back_to_raw_string_as_host():
    from src.scrapers.strategy.host_queue_map import HostQueueMap
    from src.scrapers.strategy.queue_router import QueueRouter
    from src.scrapers.strategy.scrape_task import ScrapeTask

    hqm = HostQueueMap()
    router = QueueRouter(hqm)
    task = ScrapeTask(url="not-a-url", source="test", _execute_fn=lambda: None)
    router.route([task])  # must not raise
    assert len(hqm.queues) == 1
```

- [ ] **Step 2: Run to verify they fail**

```
docker compose run --rm app python -m pytest tests/unit/test_queue_router.py -v
```

- [ ] **Step 3: Create `src/scrapers/strategy/queue_router.py`**

```python
from typing import List
from urllib.parse import urlparse

from src.scrapers.strategy.host_queue_map import HostQueueMap
from src.scrapers.strategy.scrape_task import ScrapeTask
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueueRouter:
    """
    Routes ScrapeTask objects into per-host queues in a HostQueueMap.
    Called once during Phase 1 (single-threaded) — not thread-safe.
    """

    def __init__(self, host_queue_map: HostQueueMap) -> None:
        self._map = host_queue_map

    def route(self, tasks: List[ScrapeTask]) -> None:
        """Assign each task to its host's queue."""
        for task in tasks:
            host = self._extract_host(task.url)
            idx = self._map.get_or_create(host)
            self._map.queues[idx].put(task)
            logger.debug("task_routed", url=task.url, host=host, queue_idx=idx)

    @staticmethod
    def _extract_host(url: str) -> str:
        """Return netloc from URL; fall back to the raw string if parsing fails."""
        try:
            netloc = urlparse(url).netloc
            return netloc if netloc else url
        except Exception:
            return url
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_queue_router.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/strategy/queue_router.py tests/unit/test_queue_router.py
git commit -m "🗞️ [FEAT] add QueueRouter to assign tasks to per-host queues"
```

---

### Task 6: QueueSelector — ABC + RoundRobin + WeightedRoundRobin

**Interface change from original design:** `select(queues) -> List[int]` — returns candidate indices in preferred order (non-empty queues only). The worker iterates the list and acquires the first semaphore it can.

**Files:**
- Create: `src/scrapers/strategy/queue_selector.py`
- Create: `tests/unit/test_queue_selector.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_queue_selector.py
import queue


def _make_queue(*items):
    q = queue.Queue()
    for item in items:
        q.put(item)
    return q


# ── RoundRobinQueueSelector ────────────────────────────────────────────────

def test_round_robin_excludes_empty_queues():
    from src.scrapers.strategy.queue_selector import RoundRobinQueueSelector
    queues = [queue.Queue(), _make_queue("x")]
    sel = RoundRobinQueueSelector()
    candidates = sel.select(queues)
    assert 1 in candidates
    assert 0 not in candidates


def test_round_robin_returns_empty_list_when_all_empty():
    from src.scrapers.strategy.queue_selector import RoundRobinQueueSelector
    queues = [queue.Queue(), queue.Queue()]
    assert RoundRobinQueueSelector().select(queues) == []


def test_round_robin_includes_all_non_empty_queues():
    from src.scrapers.strategy.queue_selector import RoundRobinQueueSelector
    queues = [_make_queue("a"), _make_queue("b"), queue.Queue()]
    candidates = RoundRobinQueueSelector().select(queues)
    assert set(candidates) == {0, 1}


def test_round_robin_rotates_order_across_calls():
    """Successive calls should start from different positions."""
    from src.scrapers.strategy.queue_selector import RoundRobinQueueSelector
    queues = [_make_queue("a", "b"), _make_queue("c", "d")]
    sel = RoundRobinQueueSelector()
    first_call_lead = sel.select(queues)[0]
    second_call_lead = sel.select(queues)[0]
    assert first_call_lead != second_call_lead


# ── WeightedRoundRobinQueueSelector ───────────────────────────────────────

def test_weighted_puts_largest_queue_first():
    from src.scrapers.strategy.queue_selector import WeightedRoundRobinQueueSelector
    queues = [_make_queue("a"), _make_queue("b", "c", "d")]  # sizes 1 and 3
    candidates = WeightedRoundRobinQueueSelector().select(queues)
    assert candidates[0] == 1   # larger queue is first candidate


def test_weighted_excludes_empty_queues():
    from src.scrapers.strategy.queue_selector import WeightedRoundRobinQueueSelector
    queues = [queue.Queue(), _make_queue("x")]
    candidates = WeightedRoundRobinQueueSelector().select(queues)
    assert candidates == [1]


def test_weighted_returns_empty_list_when_all_empty():
    from src.scrapers.strategy.queue_selector import WeightedRoundRobinQueueSelector
    assert WeightedRoundRobinQueueSelector().select([queue.Queue()]) == []
```

- [ ] **Step 2: Run to verify they fail**

```
docker compose run --rm app python -m pytest tests/unit/test_queue_selector.py -v
```

- [ ] **Step 3: Create `src/scrapers/strategy/queue_selector.py`**

```python
from abc import ABC, abstractmethod
from queue import Queue
from typing import List

from src.scrapers.strategy.scrape_task import ScrapeTask


class QueueSelector(ABC):
    """
    Strategy interface for ordering queue candidates for an idle worker.

    select() returns non-empty queue indices in preferred order.
    The worker iterates the list and attempts semaphore.acquire(blocking=False)
    on each index — first successful acquire wins.

    Implementations only express ordering preference; mutual exclusion is
    enforced by the per-queue BoundedSemaphore(1) in HostQueueMap.
    """

    @abstractmethod
    def select(self, queues: List[Queue[ScrapeTask]]) -> List[int]:
        """
        Return indices of non-empty queues in preferred processing order.
        Returns [] if all queues are empty.
        """
        pass


class RoundRobinQueueSelector(QueueSelector):
    """
    Returns non-empty queue indices starting from a rotating offset.
    Provides fair distribution across hosts regardless of queue depth.
    """

    def __init__(self) -> None:
        self._counter: int = 0

    def select(self, queues: List[Queue[ScrapeTask]]) -> List[int]:
        n = len(queues)
        if n == 0:
            return []
        start = self._counter % n
        self._counter += 1
        # Build candidate list starting from rotating offset, wrapping around
        ordered = [(start + i) % n for i in range(n)]
        return [idx for idx in ordered if not queues[idx].empty()]


class WeightedRoundRobinQueueSelector(QueueSelector):
    """
    Returns non-empty queue indices sorted by queue depth descending.
    Prioritises draining the deepest backlog first.
    This is the default selector.
    """

    def select(self, queues: List[Queue[ScrapeTask]]) -> List[int]:
        candidates = [
            (i, queues[i].qsize())
            for i in range(len(queues))
            if not queues[i].empty()
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [i for i, _ in candidates]
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_queue_selector.py -v
```
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/strategy/queue_selector.py tests/unit/test_queue_selector.py
git commit -m "🪙 [FEAT] add QueueSelector ABC, RoundRobin, WeightedRoundRobin — returns candidate list for semaphore-based claiming"
```

---

## Chunk 3: Worker & Dispatcher

### Task 7: ScraperWorker

**Files:**
- Create: `src/scrapers/strategy/worker.py`
- Create: `tests/unit/test_worker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_worker.py
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
        w.join(timeout=5)
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

    with patch("src.scrapers.strategy.worker.time.sleep"):
        results = _run_workers({"example.com": tasks}, num_workers=2)

    assert len(results) == 2
    # Windows must not overlap — second starts after first ends
    windows.sort()
    assert windows[1][0] >= windows[0][1], "Concurrent access to same host detected!"


def test_worker_sleeps_between_tasks():
    tasks = [_make_task(_make_article(i)) for i in range(2)]
    with patch("src.scrapers.strategy.worker.time.sleep") as mock_sleep:
        _run_workers({"example.com": tasks}, delay=5.0)
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert all(c == 5.0 for c in sleep_calls)
    assert len(sleep_calls) == 2
```

- [ ] **Step 2: Run to verify they fail**

```
docker compose run --rm app python -m pytest tests/unit/test_worker.py -v
```

- [ ] **Step 3: Create `src/scrapers/strategy/worker.py`**

```python
import queue
import threading
import time
from typing import Callable, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.strategy.host_queue_map import HostQueueMap
from src.scrapers.strategy.queue_selector import QueueSelector
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScraperWorker(threading.Thread):
    """
    Worker thread that processes ScrapeTask objects from host queues.

    Mutual exclusion per host is enforced by BoundedSemaphore(1) in HostQueueMap.
    No shared lock or busy-set is needed.

    Claiming a queue:
        1. Ask QueueSelector for ordered candidate indices (non-empty queues).
        2. For each candidate, attempt semaphore.acquire(blocking=False).
        3. First successful acquire → worker owns that queue slot.
        4. If the queue is somehow empty after acquiring (defensive), release immediately.

    Termination:
        Caller sets done_event after all tasks are in queues.
        Worker exits when done_event is set AND all queues are empty.
        (If another worker is mid-execute, its queue was already emptied by get_nowait;
        dispatcher.join() ensures we wait for it regardless.)

    Delay:
        Applied after each task, outside the semaphore, to rate-limit requests per host.
    """

    def __init__(
        self,
        worker_id: int,
        host_queue_map: HostQueueMap,
        selector: QueueSelector,
        done_event: threading.Event,
        on_result: Callable[[ScrapedArticle], None],
        delay: float = 5.0,
    ) -> None:
        super().__init__(daemon=True, name=f"ScraperWorker-{worker_id}")
        self._id = worker_id
        self._qmap = host_queue_map
        self._selector = selector
        self._done_event = done_event
        self._on_result = on_result
        self._delay = delay

    def run(self) -> None:
        logger.info("worker_started", worker_id=self._id)
        while True:
            claimed_idx = self._try_claim_queue()

            if claimed_idx is None:
                if self._done_event.is_set() and self._all_empty():
                    break
                time.sleep(0.1)   # back-off while waiting for work
                continue

            try:
                try:
                    task = self._qmap.queues[claimed_idx].get_nowait()
                except queue.Empty:
                    # Defensive: queue was emptied by another path (shouldn't happen)
                    continue

                result = task.execute()
                if result is not None:
                    self._on_result(result)

            finally:
                self._qmap.semaphores[claimed_idx].release()
                time.sleep(self._delay)   # rate-limit delay, semaphore already released

        logger.info("worker_stopped", worker_id=self._id)

    def _try_claim_queue(self) -> Optional[int]:
        """
        Ask selector for ordered candidates, try to acquire each semaphore
        non-blockingly. Returns the first claimed index, or None.
        """
        for idx in self._selector.select(self._qmap.queues):
            if self._qmap.semaphores[idx].acquire(blocking=False):
                if not self._qmap.queues[idx].empty():
                    return idx
                # Queue became empty after we acquired — release and try next
                self._qmap.semaphores[idx].release()
        return None

    def _all_empty(self) -> bool:
        return all(q.empty() for q in self._qmap.queues)
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_worker.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/strategy/worker.py tests/unit/test_worker.py
git commit -m "🏹 [FEAT] add ScraperWorker with BoundedSemaphore-based per-host mutual exclusion"
```

---

### Task 8: ScrapeDispatcher

**Files:**
- Create: `src/scrapers/strategy/scrape_dispatcher.py`
- Create: `tests/unit/test_scrape_dispatcher.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_scrape_dispatcher.py
from unittest.mock import patch


def _make_scraper(articles):
    from src.scrapers.scrapers.base_scraper import BaseScraper
    from src.scrapers.strategy.scrape_task import ScrapeTask

    class FakeScraper(BaseScraper):
        def discover(self):
            return [
                ScrapeTask(url=f"http://example.com/{i}", source="test",
                           _execute_fn=lambda a=a: a)
                for i, a in enumerate(articles)
            ]
    return FakeScraper()


def _make_articles(n):
    from src.scrapers.scrapers.article import ScrapedArticle
    return [
        ScrapedArticle(url=f"http://example.com/{i}", title=f"T{i}",
                       content="C", published_at=None, source="test")
        for i in range(n)
    ]


def test_dispatcher_delivers_all_results():
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
    articles = _make_articles(3)
    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(num_workers=2, delay=0.0).run(
            [_make_scraper(articles)], on_result=results.append
        )
    assert len(results) == 3


def test_dispatcher_handles_empty_scraper():
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(num_workers=1, delay=0.0).run(
            [_make_scraper([])], on_result=results.append
        )
    assert results == []


def test_dispatcher_accepts_custom_selector():
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
    from src.scrapers.strategy.queue_selector import RoundRobinQueueSelector
    articles = _make_articles(2)
    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(
            num_workers=1, delay=0.0,
            selector=RoundRobinQueueSelector(),
        ).run([_make_scraper(articles)], on_result=results.append)
    assert len(results) == 2


def test_dispatcher_handles_discover_exception_gracefully():
    from src.scrapers.scrapers.base_scraper import BaseScraper
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher

    class BrokenScraper(BaseScraper):
        def discover(self):
            raise RuntimeError("network down")

    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(num_workers=1, delay=0.0).run(
            [BrokenScraper()], on_result=results.append
        )
    assert results == []
```

- [ ] **Step 2: Run to verify they fail**

```
docker compose run --rm app python -m pytest tests/unit/test_scrape_dispatcher.py -v
```

- [ ] **Step 3: Create `src/scrapers/strategy/scrape_dispatcher.py`**

```python
import threading
from typing import Callable, List, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.scrapers.base_scraper import BaseScraper
from src.scrapers.strategy.host_queue_map import HostQueueMap
from src.scrapers.strategy.queue_router import QueueRouter
from src.scrapers.strategy.queue_selector import QueueSelector, WeightedRoundRobinQueueSelector
from src.scrapers.strategy.worker import ScraperWorker
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScrapeDispatcher:
    """
    Orchestrates a full scrape job in two phases.

    Phase 1 (single-threaded):
      Call discover() on each scraper → route tasks into per-host queues.

    Phase 2 (multi-threaded):
      Spin up num_workers ScraperWorker threads.
      Each worker asks QueueSelector for candidates, acquires the first
      available BoundedSemaphore(1), processes one task, sleeps `delay` seconds.

    Args:
        num_workers: Number of concurrent worker threads (default 3).
        delay:       Seconds between requests per worker (default 5.0).
        selector:    QueueSelector instance. Defaults to WeightedRoundRobinQueueSelector.
    """

    def __init__(
        self,
        num_workers: int = 3,
        delay: float = 5.0,
        selector: Optional[QueueSelector] = None,
    ) -> None:
        self._num_workers = num_workers
        self._delay = delay
        self._selector = selector or WeightedRoundRobinQueueSelector()

    def run(
        self,
        scrapers: List[BaseScraper],
        on_result: Callable[[ScrapedArticle], None],
    ) -> None:
        """
        Discover tasks from all scrapers, route them, dispatch workers.
        Blocks until all tasks are processed.
        """
        # ── Phase 1: discover & route ────────────────────────────────────
        host_queue_map = HostQueueMap()
        router = QueueRouter(host_queue_map)
        total_tasks = 0

        for scraper in scrapers:
            try:
                tasks = scraper.discover()
            except Exception as e:
                logger.error("discover_failed",
                             scraper=type(scraper).__name__, error=str(e))
                tasks = []
            router.route(tasks)
            total_tasks += len(tasks)

        logger.info("dispatch_phase1_complete",
                    total_tasks=total_tasks,
                    host_count=len(host_queue_map.queues))

        if total_tasks == 0:
            return

        # ── Phase 2: workers ─────────────────────────────────────────────
        done_event = threading.Event()

        workers = [
            ScraperWorker(
                worker_id=i,
                host_queue_map=host_queue_map,
                selector=self._selector,
                done_event=done_event,
                on_result=on_result,
                delay=self._delay,
            )
            for i in range(self._num_workers)
        ]

        for w in workers:
            w.start()

        # Signal that no more tasks will be added.
        # Workers use this + all_empty() as their exit condition.
        done_event.set()

        for w in workers:
            w.join()

        logger.info("dispatch_phase2_complete")
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_scrape_dispatcher.py -v
```
Expected: 4 passed

- [ ] **Step 5: Run all strategy tests together**

```
pytest tests/unit/test_scrape_task.py tests/unit/test_host_queue_map.py tests/unit/test_queue_router.py tests/unit/test_queue_selector.py tests/unit/test_worker.py tests/unit/test_scrape_dispatcher.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/scrapers/strategy/scrape_dispatcher.py tests/unit/test_scrape_dispatcher.py
git commit -m "🧫 [FEAT] add ScrapeDispatcher orchestrating per-host queue routing and semaphore-guarded worker pool"
```

---

## Chunk 4: Scraper Refactor

### Task 9: Refactor ArxivScraper — fetch_pdf=True + discover()

**Files:**
- Modify: `src/scrapers/scrapers/arxiv_scraper.py`
- Modify: `tests/unit/test_arxiv_scraper.py`

- [ ] **Step 1: Replace `tests/unit/test_arxiv_scraper.py` with updated tests**

```python
# tests/unit/test_arxiv_scraper.py
import responses
from datetime import datetime, timedelta, timezone

RECENT = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atom(entries_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        + entries_xml
        + "</feed>"
    )


def _entry(paper_id="2401.00001", version="v1", title="Digital Twins Research",
           summary="Abstract text.", published=None, authors=None):
    published = published or RECENT
    author_xml = "".join(
        f"<author><name>{a}</name></author>" for a in (authors or ["John Doe"])
    )
    return (
        f"<entry>"
        f"<id>http://arxiv.org/abs/{paper_id}{version}</id>"
        f"<title>{title}</title>"
        f"<summary>{summary}</summary>"
        f"<published>{published}</published>"
        f"{author_xml}"
        f'<link href="http://arxiv.org/abs/{paper_id}{version}" rel="alternate" type="text/html"/>'
        f"</entry>"
    )


# ── constructor ────────────────────────────────────────────────────────────

def test_fetch_pdf_is_true_by_default():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper().fetch_pdf is True


def test_respects_max_results():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper(max_results=50).max_results == 50


def test_builds_query_contains_digital_twin_terms():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    q = ArxivScraper()._build_query()
    assert "digital" in q.lower() or "twin" in q.lower()


# ── discover() ────────────────────────────────────────────────────────────

@responses.activate
def test_discover_returns_one_task_per_entry():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry()), status=200)
    tasks = ArxivScraper(fetch_pdf=False).discover()
    assert len(tasks) == 1
    assert tasks[0].url == "http://arxiv.org/abs/2401.00001v1"
    assert tasks[0].source == "arxiv"


@responses.activate
def test_discover_returns_empty_on_api_error():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query", status=500)
    assert ArxivScraper().discover() == []


@responses.activate
def test_discover_filters_old_papers():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(published=old)), status=200)
    assert ArxivScraper(days_back=7).discover() == []


# ── task.execute() ────────────────────────────────────────────────────────

@responses.activate
def test_execute_returns_article_with_abstract_when_fetch_pdf_false():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(summary="Short abstract.")), status=200)
    article = ArxivScraper(fetch_pdf=False).discover()[0].execute()
    assert article is not None
    assert article.content == "Short abstract."
    assert article.source == "arxiv"
    assert article.metadata["pdf_available"] is False


@responses.activate
def test_execute_extracts_authors():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(authors=["Alice", "Bob"])), status=200)
    article = ArxivScraper(fetch_pdf=False).discover()[0].execute()
    assert article.metadata["authors"] == ["Alice", "Bob"]


@responses.activate
def test_execute_falls_back_to_abstract_when_pdf_fails():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00002", summary="Fallback.")), status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00002v1", status=404)
    article = ArxivScraper(fetch_pdf=True).discover()[0].execute()
    assert article.content == "Fallback."
    assert article.metadata["pdf_available"] is False


@responses.activate
def test_execute_uses_pdf_text_and_sets_pdf_available_true():
    from unittest.mock import patch
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00003", summary="Short abstract.")),
                  status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00003v1",
                  body=b"%PDF-1.4 fake", status=200)
    with patch(
        "src.scrapers.content_parsers.pdf_parser.PdfParser.parse",
        return_value="Full PDF text."
    ):
        article = ArxivScraper(fetch_pdf=True).discover()[0].execute()
    assert article.metadata["pdf_available"] is True
    assert article.content == "Full PDF text."
    assert article.metadata["abstract"] == "Short abstract."


@responses.activate
def test_discover_handles_entry_with_missing_summary():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    entry_xml = (
        f"<entry>"
        f"<id>http://arxiv.org/abs/2401.00004v1</id>"
        f"<title>Minimal Entry</title>"
        f"<summary></summary>"
        f"<published>{RECENT}</published>"
        f"</entry>"
    )
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(entry_xml), status=200)
    tasks = ArxivScraper(fetch_pdf=False).discover()
    assert len(tasks) == 1
    article = tasks[0].execute()
    assert article.title == "Minimal Entry"
    assert article.content == ""
```

- [ ] **Step 2: Run to confirm new tests fail**

```
docker compose run --rm app python -m pytest tests/unit/test_arxiv_scraper.py -v
```

- [ ] **Step 3: Rewrite `src/scrapers/scrapers/arxiv_scraper.py`**

```python
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.scrapers.base_scraper import BaseScraper
from src.scrapers.content_parsers.pdf_parser import PdfParser
from src.scrapers.strategy.scrape_task import ScrapeTask
from src.utils.logging import get_logger

logger = get_logger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


class ArxivScraper(BaseScraper):
    """Scraper for arXiv API. Fetches PDF full-text by default."""

    def __init__(self, max_results: int = 100, days_back: int = 7,
                 fetch_pdf: bool = True) -> None:
        self.max_results = max_results
        self.days_back = days_back
        self.fetch_pdf = fetch_pdf
        self._pdf_parser = PdfParser() if fetch_pdf else None

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        """
        Call arXiv API, parse Atom feed, return one ScrapeTask per article.
        Each task's execute() fetches PDF (if enabled) and builds the article.
        Returns [] on API or parse failure.
        """
        entries = self._fetch_entries()
        tasks = [
            ScrapeTask(
                url=e["url"],
                source="arxiv",
                metadata={"arxiv_id": e["arxiv_id"]},
                _execute_fn=lambda d=e: self._build_article(d),
            )
            for e in entries
        ]
        logger.info("arxiv_discover_complete", task_count=len(tasks))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _build_query(self) -> str:
        terms = [
            'ti:"digital twin"',
            'ti:"digital twins"',
            'abs:"digital twin"',
            'abs:"cyber-physical"',
        ]
        return " OR ".join(terms)

    def _fetch_entries(self) -> List[dict]:
        """Fetch and parse the arXiv Atom feed. Returns list of entry dicts."""
        params = {
            "search_query": self._build_query(),
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            response = requests.get(
                ARXIV_API_URL, params=params, timeout=60,
                headers={"User-Agent": "Digital-Twins-Scraper/1.0"},
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("arxiv_fetch_failed", error=str(e))
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error("arxiv_parse_failed", error=str(e))
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)
        entries = []
        for entry in root.findall(f"{ATOM_NS}entry"):
            data = self._parse_entry(entry)
            if data is None:
                continue
            try:
                pub_date = datetime.fromisoformat(
                    data["published"].replace("Z", "+00:00")
                )
                if pub_date < cutoff:
                    continue
            except (ValueError, AttributeError):
                pass
            entries.append(data)
        return entries

    def _parse_entry(self, entry) -> Optional[dict]:
        id_elem = entry.find(f"{ATOM_NS}id")
        title_elem = entry.find(f"{ATOM_NS}title")
        summary_elem = entry.find(f"{ATOM_NS}summary")
        published_elem = entry.find(f"{ATOM_NS}published")

        arxiv_id = id_elem.text if id_elem is not None else ""
        title = title_elem.text.strip() if title_elem is not None else ""
        summary = (summary_elem.text or "").strip() if summary_elem is not None else ""
        published = published_elem.text if published_elem is not None else ""

        authors = [
            name_elem.text
            for author in entry.findall(f"{ATOM_NS}author")
            for name_elem in [author.find(f"{ATOM_NS}name")]
            if name_elem is not None
        ]

        url = next(
            (link.get("href", "") for link in entry.findall(f"{ATOM_NS}link")
             if link.get("rel") == "alternate"),
            arxiv_id,
        )
        pdf_url = arxiv_id.replace("/abs/", "/pdf/") if "/abs/" in arxiv_id else ""

        return {
            "url": url or arxiv_id,
            "arxiv_id": arxiv_id,
            "title": title,
            "summary": summary,
            "published": published,
            "authors": authors,
            "pdf_url": pdf_url,
        }

    def _build_article(self, entry_data: dict) -> Optional[ScrapedArticle]:
        summary = entry_data["summary"]
        pdf_url = entry_data["pdf_url"]
        pdf_available = False

        if self.fetch_pdf and pdf_url:
            full_text = self._pdf_parser.parse(pdf_url)
            if full_text:
                content = full_text
                pdf_available = True
            else:
                content = summary
        else:
            content = summary

        return ScrapedArticle(
            url=entry_data["url"],
            title=entry_data["title"],
            content=content,
            published_at=entry_data["published"],
            source="arxiv",
            metadata={
                "authors": entry_data["authors"],
                "arxiv_id": entry_data["arxiv_id"],
                "abstract": summary,
                "pdf_available": pdf_available,
            },
        )
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_arxiv_scraper.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/scrapers/arxiv_scraper.py tests/unit/test_arxiv_scraper.py
git commit -m "🪡 [FEAT] refactor ArxivScraper to discover()+_build_article(), enable fetch_pdf=True by default"
```

---

### Task 10: Refactor BlogScraper — discover()

**Files:**
- Modify: `src/scrapers/scrapers/blog_scraper.py`
- Modify: `tests/unit/test_blog_scraper.py`

- [ ] **Step 1: Add discover/execute tests to `test_blog_scraper.py`**, and remove `test_blog_scraper_respects_rate_limit` (delay now lives in the worker):

```python
# Add to tests/unit/test_blog_scraper.py

@responses.activate
def test_discover_returns_tasks_for_allowed_links():
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    listing_html = '<html><body><article><a href="/blog/dt-article">DT</a></article></body></html>'
    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)

    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "article a", "title": "h1", "content": ".content"},
    )
    tasks = scraper.discover()
    assert len(tasks) == 1
    assert "dt-article" in tasks[0].url


@responses.activate
def test_discover_returns_empty_when_listing_fetch_fails():
    from src.scrapers.scrapers.blog_scraper import BlogScraper
    responses.add(responses.GET, "https://example.com/blog", status=500)
    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "a", "title": "h1", "content": ".content"},
    )
    assert scraper.discover() == []


@responses.activate
def test_execute_fetches_and_returns_matching_article():
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    listing_html = '<html><body><a href="/digital-twins">DT Link</a></body></html>'
    article_html = (
        '<html><body>'
        '<h1>Digital Twin Guide</h1>'
        '<div class="content"><p>Digital twins are virtual replicas.</p></div>'
        '</body></html>'
    )
    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)
    responses.add(responses.GET, "https://example.com/digital-twins",
                  body=article_html, status=200)

    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "a", "title": "h1", "content": ".content"},
    )
    article = scraper.discover()[0].execute()
    assert article is not None
    assert article.title == "Digital Twin Guide"
    assert article.source == "test"


@responses.activate
def test_execute_returns_none_for_non_keyword_article():
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    listing_html = '<html><body><a href="/unrelated">No DT here</a></body></html>'
    article_html = '<html><body><h1>Cloud News</h1><div class="content"><p>About AWS.</p></div></body></html>'
    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)
    responses.add(responses.GET, "https://example.com/unrelated",
                  body=article_html, status=200)

    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "a", "title": "h1", "content": ".content"},
    )
    tasks = scraper.discover()
    assert tasks[0].execute() is None
```

- [ ] **Step 2: Run to confirm new tests fail, old internal-method tests still pass**

```
docker compose run --rm app python -m pytest tests/unit/test_blog_scraper.py -v
```

- [ ] **Step 3: Update `src/scrapers/scrapers/blog_scraper.py`** — add `discover()` + `_fetch_article()`, remove the old `scrape()` override, keep all internal helpers (`_extract_links`, `_extract_article`, `_can_fetch`, etc.) unchanged:

```python
import requests
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.scrapers.base_scraper import BaseScraper
from src.scrapers.content_parsers.html_parser import HtmlArticleParser
from src.scrapers.strategy.scrape_task import ScrapeTask
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BlogScraper(BaseScraper):
    """Scraper for blog websites with CSS selectors."""

    def __init__(self, base_url: str, source: str, selectors: Dict[str, str],
                 rate_limit: float = 2.0) -> None:
        self.base_url = base_url
        self.source = source
        self.selectors = selectors
        self.rate_limit = rate_limit  # kept for back-compat; delay enforced by worker
        self._robot_parser: Optional[RobotFileParser] = None
        self._robots_loaded: bool = False
        self._html_parser = HtmlArticleParser(
            selectors=[selectors.get("content", "article")]
        )

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        """
        Fetch listing page, extract article links, return one ScrapeTask per link.
        Filters out URLs disallowed by robots.txt.
        """
        try:
            response = requests.get(
                self.base_url, timeout=30,
                headers={"User-Agent": "Digital-Twins-Scraper/1.0"},
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("blog_listing_fetch_failed", url=self.base_url, error=str(e))
            return []

        links = self._extract_links(response.text)
        logger.info("blog_links_discovered", source=self.source, count=len(links))

        tasks = []
        for link in links[:20]:
            if not self._can_fetch(link):
                logger.info("blog_url_blocked_by_robots", url=link)
                continue
            tasks.append(ScrapeTask(
                url=link,
                source=self.source,
                _execute_fn=lambda u=link: self._fetch_article(u),
            ))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _fetch_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = requests.get(
                url, timeout=30,
                headers={"User-Agent": "Digital-Twins-Scraper/1.0"},
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning("blog_article_fetch_failed", url=url, error=str(e))
            return None

        title, content = self._extract_article(response.text)
        if not self._matches_keywords(title) and not self._matches_keywords(content):
            return None

        return ScrapedArticle(
            url=url, title=title, content=content,
            published_at=None, source=self.source,
        )

    def _get_robot_parser(self) -> RobotFileParser:
        if self._robot_parser is None:
            self._robot_parser = RobotFileParser()
            parsed = urlparse(self.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                response = requests.get(
                    robots_url, timeout=10,
                    headers={"User-Agent": "Digital-Twins-Scraper/1.0"},
                )
                if response.status_code == 200:
                    self._robot_parser.parse(response.text.splitlines())
                    self._robots_loaded = True
            except Exception as e:
                logger.warning("robots_txt_fetch_failed", url=robots_url, error=str(e))
        return self._robot_parser

    def _can_fetch(self, url: str) -> bool:
        self._get_robot_parser()
        if not self._robots_loaded:
            return True
        try:
            return self._robot_parser.can_fetch("Digital-Twins-Scraper", url)
        except Exception:
            return True

    def _extract_links(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        selector = self.selectors.get("article_link", "a")
        base = self.base_url if self.base_url.endswith("/") else self.base_url + "/"
        return [
            urljoin(base, link.get("href"))
            for link in soup.select(selector)
            if link.get("href")
        ]

    def _extract_article(self, html: str) -> Tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        title_selector = self.selectors.get("title", "h1")
        title_elem = soup.select_one(title_selector)
        title = title_elem.get_text(strip=True) if title_elem else ""
        content = self._html_parser.parse(html)
        return title, content

    def _matches_keywords(self, text: str) -> bool:
        keywords = ["digital twin", "digital twins", "cyber-physical", "virtual replica"]
        return any(kw in text.lower() for kw in keywords)
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_blog_scraper.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/scrapers/blog_scraper.py tests/unit/test_blog_scraper.py
git commit -m "🍬 [FEAT] refactor BlogScraper to discover()+_fetch_article()"
```

---

### Task 11: Refactor RssScraper — discover()

**Files:**
- Modify: `src/scrapers/scrapers/rss_scraper.py`
- Modify: `tests/unit/test_rss_scraper.py`

- [ ] **Step 1: Update `test_rss_scraper.py`** — replace `scraper.scrape()` calls with `discover()` + `execute()`:

```python
# tests/unit/test_rss_scraper.py  (full replacement)
import responses


RSS_DT = '''<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Digital Twins in Manufacturing</title>
    <link>https://example.com/dt-article</link>
    <description>An article about digital twins technology.</description>
    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Unrelated Article</title>
    <link>https://example.com/unrelated</link>
    <description>Nothing here.</description>
  </item>
</channel></rss>'''


@responses.activate
def test_discover_returns_keyword_matched_tasks_only():
    from src.scrapers.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed", body=RSS_DT, status=200)
    tasks = RssScraper(url="https://example.com/feed", source="test").discover()
    assert len(tasks) == 1
    assert "dt-article" in tasks[0].url


@responses.activate
def test_discover_returns_empty_on_http_error():
    from src.scrapers.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed", status=500)
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_discover_returns_empty_on_network_exception():
    from src.scrapers.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed",
                  body=Exception("Network error"))
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_discover_returns_empty_on_empty_feed():
    from src.scrapers.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed",
                  body='<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>',
                  status=200)
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_execute_returns_article_with_all_fields():
    from src.scrapers.scrapers.rss_scraper import RssScraper
    rss = '''<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Digital Twin Innovation</title>
        <link>https://example.com/article</link>
        <description>Content about digital twins</description>
        <pubDate>Tue, 15 Jan 2024 10:00:00 GMT</pubDate>
        <author>John Doe</author>
      </item>
    </channel></rss>'''
    article_html = '<html><article><p>Full article about digital twins.</p></article></html>'
    responses.add(responses.GET, "https://example.com/feed", body=rss, status=200)
    responses.add(responses.GET, "https://example.com/article",
                  body=article_html, status=200)

    scraper = RssScraper(url="https://example.com/feed", source="techcrunch")
    article = scraper.discover()[0].execute()
    assert article.title == "Digital Twin Innovation"
    assert article.url == "https://example.com/article"
    assert article.source == "techcrunch"


# ── keyword matching (unchanged behaviour) ────────────────────────────────

def test_matches_digital_twins_variants():
    from src.scrapers.scrapers.rss_scraper import RssScraper
    s = RssScraper(url="https://example.com/feed", source="test")
    assert s._matches_keywords("Digital Twins in Manufacturing") is True
    assert s._matches_keywords("digital twin technology") is True
    assert s._matches_keywords("cyber-physical systems") is True
    assert s._matches_keywords("cyberphysical integration") is True
    assert s._matches_keywords("DIGITAL TWINS") is True
    assert s._matches_keywords("Unrelated article about cats") is False
    assert s._matches_keywords("") is False
```

- [ ] **Step 2: Run to confirm new tests fail, keyword tests pass**

```
docker compose run --rm app python -m pytest tests/unit/test_rss_scraper.py -v
```

- [ ] **Step 3: Rewrite `src/scrapers/scrapers/rss_scraper.py`**

```python
import feedparser
import requests
import re
from typing import List, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.scrapers.base_scraper import BaseScraper
from src.scrapers.content_parsers.html_parser import HtmlArticleParser
from src.scrapers.strategy.scrape_task import ScrapeTask
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

DIGITAL_TWINS_KEYWORDS = [
    r"digital\s+twin",
    r"digital\s+twins",
    r"twin\s+technology",
    r"cyber[\-\s]?physical",
    r"virtual\s+replica",
]


class RssScraper(BaseScraper):
    """Scraper for RSS feeds with Digital Twins keyword filtering."""

    def __init__(self, url: str, source: str, rate_limit: float = 1.0) -> None:
        self.url = url
        self.source = source
        self.rate_limit = rate_limit  # kept for back-compat; delay enforced by worker
        self._keyword_pattern = re.compile(
            "|".join(DIGITAL_TWINS_KEYWORDS), re.IGNORECASE
        )
        self._html_parser = HtmlArticleParser()

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        """
        Fetch RSS feed, filter entries by keyword, return one ScrapeTask per match.
        Returns [] on fetch or parse failure.
        """
        try:
            response = requests.get(
                self.url, timeout=30,
                headers={"User-Agent": "Digital-Twins-Scraper/1.0"},
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("rss_fetch_failed", url=self.url, error=str(e))
            return []

        feed = feedparser.parse(response.content)
        if not feed.entries:
            return []

        tasks = []
        for entry in feed.entries:
            title = entry.get("title", "")
            description = entry.get("description", "") or entry.get("summary", "")
            if not self._matches_keywords(title) and not self._matches_keywords(description):
                continue
            tasks.append(ScrapeTask(
                url=entry.get("link", ""),
                source=self.source,
                _execute_fn=lambda e=entry: self._fetch_article(e),
            ))

        logger.info("rss_discover_complete", source=self.source, task_count=len(tasks))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _fetch_article(self, entry) -> Optional[ScrapedArticle]:
        link = entry.get("link", "")
        description = entry.get("description", "") or entry.get("summary", "")
        fallback = sanitize_content(description)
        content = self._html_parser.fetch_and_parse(link, fallback=fallback)
        return ScrapedArticle(
            url=link,
            title=entry.get("title", ""),
            content=content,
            published_at=entry.get("published", ""),
            source=self.source,
            metadata={"author": entry.get("author")},
        )

    def _matches_keywords(self, text: str) -> bool:
        if not text:
            return False
        return bool(self._keyword_pattern.search(text))
```

- [ ] **Step 4: Run tests**

```
docker compose run --rm app python -m pytest tests/unit/test_rss_scraper.py -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/scrapers/rss_scraper.py tests/unit/test_rss_scraper.py
git commit -m "🐙 [FEAT] refactor RssScraper to discover()+_fetch_article()"
```

---

### Task 12: Remove scrape() bridge from BaseScraper

All concrete scrapers now implement `discover()`. The bridge can be removed.

**Files:**
- Modify: `src/scrapers/scrapers/base_scraper.py`

- [ ] **Step 1: Update `base_scraper.py`** to remove the `scrape()` bridge:

```python
from abc import ABC, abstractmethod
from typing import List

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.strategy.scrape_task import ScrapeTask

__all__ = ["BaseScraper", "ScrapedArticle"]


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def discover(self) -> List[ScrapeTask]:
        """
        Enumerate all work items for this source.
        Makes the minimum HTTP requests needed to find article URLs.
        Returns [] on any failure.
        """
        pass
```

- [ ] **Step 2: Run all scraper tests**

```
docker compose run --rm app python -m pytest tests/unit/test_arxiv_scraper.py tests/unit/test_blog_scraper.py tests/unit/test_rss_scraper.py -v
```
Expected: all pass (no test calls `scrape()` anymore)

- [ ] **Step 3: Commit**

```bash
git add src/scrapers/scrapers/base_scraper.py
git commit -m "🌺 [REFACTOR] remove scrape() migration bridge — discover() is now the sole interface"
```

---

## Chunk 5: Integration

### Task 13: Wire ScrapeDispatcher into main.py

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Replace `run_scrape_cycle` in `src/main.py`**

```python
def run_scrape_cycle(sources: list, analyzer, prompt: str, correlation_id: str) -> None:
    """Build scrapers from source configs, dispatch via ScrapeDispatcher."""
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
    from sqlalchemy import text

    scrapers_with_sources = []
    for source in sources:
        source_type = source["source_type"]
        logger.info("scrape_source_start",
                    source=source["source"], source_type=source_type)
        try:
            if source_type == "rss":
                scraper = RssScraper(url=source["url"], source=source["source"])
            elif source_type == "blog":
                scraper = BlogScraper(
                    base_url=source["base_url"],
                    source=source["source"],
                    selectors=source["selectors"],
                )
            elif source_type == "arxiv":
                cfg = source.get("selector_config", {})
                scraper = ArxivScraper(
                    max_results=cfg.get("max_results", 30),
                    days_back=cfg.get("days_back", 1),
                )
            else:
                logger.warning("unknown_source_type_skipped", source_type=source_type)
                continue
        except Exception as e:
            logger.error("scraper_init_failed", source=source["source"], error=str(e))
            continue

        scrapers_with_sources.append((scraper, source))

    if not scrapers_with_sources:
        return

    def handle_result(scraped) -> None:
        if _shutdown_requested or check_timeout(time.time()):
            return
        process_article_safe(scraped, analyzer, prompt, correlation_id)

    ScrapeDispatcher(num_workers=MAX_WORKERS, delay=5.0).run(
        scrapers=[s for s, _ in scrapers_with_sources],
        on_result=handle_result,
    )

    # Update last_scraped_at for each successfully initialized source
    for _, source in scrapers_with_sources:
        session = get_session()
        try:
            session.execute(
                text("UPDATE scraper_settings SET last_scraped_at = NOW() WHERE id = :id"),
                {"id": source["id"]},
            )
            session.commit()
        finally:
            session.close()
```

- [ ] **Step 2: Run unit tests**

```
docker compose run --rm app python -m pytest tests/unit/ -v --tb=short
```
Expected: all pass

- [ ] **Step 3: Run integration tests**

```
docker compose run --rm app python -m pytest tests/integration/ -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "🍢 [FEAT] integrate ScrapeDispatcher into main.py — replace sequential scrape loop with per-host queue worker pool"
```

---

### Task 14: Full regression

- [ ] **Run complete test suite**

```
docker compose run --rm app python -m pytest tests/ -v --tb=short
```
Expected: all pass

- [ ] **Smoke-test strategy imports**

```bash
python -c "
from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
from src.scrapers.strategy.queue_selector import WeightedRoundRobinQueueSelector, RoundRobinQueueSelector
from src.scrapers.strategy.host_queue_map import HostQueueMap
print('All strategy imports OK')
"
```

- [ ] **Final commit**

```bash
git add -p
git commit -m "🍧 [CHORE] post-integration verification and cleanup"
```
