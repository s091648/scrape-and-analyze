# Pipeline Observability Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire observability signals (Telegram notifications, OTel counters) into the collection pipeline via a `PipelineCompletedEvent` published at the end of each run, replacing the dead `RunSummary` pattern in `main.py`.

**Architecture:** `CollectionPipeline` gains a `PipelineStats` accumulator (application layer). `ArticleScrapedHandler` records per-article outcomes into it. At the end of `run()`, the pipeline publishes `PipelineCompletedEvent` to the event bus. Two infra handlers subscribe: `OtelMetricsHandler` fires per-source OTel counters; `NotificationHandler` dispatches to registered `BaseNotifier` implementations (currently `TelegramNotifier`).

**Tech Stack:** Python, structlog, opentelemetry-sdk, requests (Telegram), pytest, docker compose test runner.

**Spec:** `docs/superpowers/specs/2026-04-25-pipeline-observability-design.md`

**Test command:** `docker compose run --rm test_service pytest <path> -v`

---

## File Map

### New files
| Path | Responsibility |
|---|---|
| `src/modules/collection/application/article_outcome.py` | `ArticleOutcome` enum |
| `src/modules/collection/application/pipeline_stats.py` | `SourceStats` dataclass + thread-safe `PipelineStats` accumulator |
| `src/modules/collection/application/events/pipeline_completed.py` | `PipelineCompletedEvent` frozen dataclass |
| `src/infrastructure/collection/handlers/__init__.py` | package exports |
| `src/infrastructure/collection/handlers/otel_metrics_handler.py` | fires OTel counters on `PipelineCompletedEvent` |
| `src/tests/unit/test_article_outcome.py` | unit tests for `ArticleOutcome` |
| `src/tests/unit/test_pipeline_stats.py` | unit tests for `PipelineStats` |
| `src/tests/unit/test_notification_handler.py` | unit tests for `NotificationHandler` |
| `src/tests/unit/test_telegram_notifier.py` | unit tests for `TelegramNotifier.notify()` |
| `src/tests/unit/test_otel_metrics_handler.py` | unit tests for `OtelMetricsHandler` |
| `src/tests/unit/test_article_scraped_handler.py` | unit tests for updated `ArticleScrapedHandler` |

### Modified files
| Path | Change |
|---|---|
| `src/modules/collection/application/events/__init__.py` | remove shim, export `PipelineCompletedEvent` |
| `src/modules/collection/application/use_cases/process_scraped_article.py` | returns `ArticleOutcome` |
| `src/modules/collection/application/event_handlers/article_scraped_handler.py` | inject `PipelineStats`, record outcome |
| `src/infrastructure/collection/collection_pipeline.py` | inject `PipelineStats`, publish `PipelineCompletedEvent` |
| `src/infrastructure/shared/notifications/base_notifier.py` | interface → `notify(PipelineCompletedEvent)` |
| `src/infrastructure/shared/notifications/telegram.py` | implement new `notify()` interface |
| `src/infrastructure/shared/notifications/notification_service.py` | refactor to `NotificationHandler` class |
| `src/infrastructure/shared/notifications/__init__.py` | update exports |
| `src/infrastructure/shared/observability/__init__.py` | remove `RunSummary` / `SourceResult` exports |
| `src/bootstrap.py` | wire `PipelineStats`, new handlers |
| `src/entrypoints/cli/main.py` | remove `RunSummary`, `notify_all` |
| 6 test files (see Task 1) | `ArticleScrapedEvent` → `ScrapedArticleDTO` |

### Deleted files
| Path | Reason |
|---|---|
| `src/modules/collection/application/events/article_scraped.py` | unreachable dead class |
| `src/infrastructure/shared/observability/run_summary.py` | replaced by `PipelineStats` |

---

## Task 1: Remove dead code — `ArticleScrapedEvent` shim

**Files:**
- Modify: `src/modules/collection/application/events/__init__.py`
- Modify: `src/tests/unit/test_scrape_task.py`
- Modify: `src/tests/unit/test_topic_id_propagation.py`
- Modify: `src/tests/unit/test_scrapers.py`
- Modify: `src/tests/unit/test_process_article_topic_and_metadata.py`
- Modify: `src/tests/integration/test_topic_article_pipeline.py`
- Modify: `src/tests/integration/test_arxiv_metadata.py`
- Delete: `src/modules/collection/application/events/article_scraped.py`

- [ ] **Step 1: Update 6 test files — replace `ArticleScrapedEvent` import with `ScrapedArticleDTO`**

In `src/tests/unit/test_scrape_task.py`, replace:
```python
from src.modules.collection.application.events import ArticleScrapedEvent
event = ArticleScrapedEvent(url="http://x.com", title="T", content="C", source="test")
```
with:
```python
from src.modules.collection.application.dtos import ScrapedArticleDTO
event = ScrapedArticleDTO(url="http://x.com", title="T", content="C", source="test")
```

In `src/tests/unit/test_topic_id_propagation.py`, replace:
```python
def test_article_scraped_event_accepts_topic_id():
    from uuid import uuid4
    from src.modules.collection.application.events import ArticleScrapedEvent
    tid = uuid4()
    ev = ArticleScrapedEvent(
        url="https://x.com", title="T", content="C",
        source="rss", topic_id=tid,
    )
    assert ev.topic_id == tid
```
with:
```python
def test_scraped_article_dto_accepts_topic_id():
    from uuid import uuid4
    from src.modules.collection.application.dtos import ScrapedArticleDTO
    tid = uuid4()
    dto = ScrapedArticleDTO(
        url="https://x.com", title="T", content="C",
        source="rss", topic_id=tid,
    )
    assert dto.topic_id == tid
```

In `src/tests/unit/test_scrapers.py`, replace:
```python
def test_scraped_article_dataclass_has_fields():
    """ScrapedArticle should have required fields"""
    from src.modules.collection.application.events import ArticleScrapedEvent

    article = ArticleScrapedEvent(
        url="https://example.com",
        title="Test",
        content="Content",
        published_at="2024-01-01",
        source="test",
        topic_id=None,
        metadata={"key": "value"},
    )

    assert article.url == "https://example.com"
    assert article.title == "Test"
    assert article.source == "test"
```
with:
```python
def test_scraped_article_dto_has_fields():
    from src.modules.collection.application.dtos import ScrapedArticleDTO

    dto = ScrapedArticleDTO(
        url="https://example.com",
        title="Test",
        content="Content",
        source="test",
        topic_id=None,
        metadata={"key": "value"},
    )

    assert dto.url == "https://example.com"
    assert dto.title == "Test"
    assert dto.source == "test"
```

In `src/tests/unit/test_process_article_topic_and_metadata.py`, replace the top import and `_make_arxiv_event` helper:
```python
from src.modules.collection.application.events import ArticleScrapedEvent
```
with:
```python
from src.modules.collection.application.dtos import ScrapedArticleDTO
```
and rename `ArticleScrapedEvent(` → `ScrapedArticleDTO(` wherever it appears in that file.

In `src/tests/integration/test_topic_article_pipeline.py`, replace:
```python
from src.modules.collection.application.events import ArticleScrapedEvent
```
with:
```python
from src.modules.collection.application.dtos import ScrapedArticleDTO
```
and rename `ArticleScrapedEvent(` → `ScrapedArticleDTO(` in the test body.

In `src/tests/integration/test_arxiv_metadata.py`, replace:
```python
from src.modules.collection.application.events import ArticleScrapedEvent
```
with:
```python
from src.modules.collection.application.dtos import ScrapedArticleDTO
```
and rename `ArticleScrapedEvent(` → `ScrapedArticleDTO(` in `_make_uc` and the test body.

- [ ] **Step 2: Run all unit tests to confirm they still pass (shim is still in place)**

```
docker compose run --rm test_service pytest src/tests/unit/ -v
```
Expected: all pass.

- [ ] **Step 3: Remove the shim and empty the events `__init__.py`**

Replace the full content of `src/modules/collection/application/events/__init__.py` with:
```python
__all__: list[str] = []
```

- [ ] **Step 4: Delete the dead class file**

```bash
rm src/modules/collection/application/events/article_scraped.py
```

- [ ] **Step 5: Run all tests again to confirm nothing broke**

```
docker compose run --rm test_service pytest src/tests/unit/ src/tests/integration/ -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/modules/collection/application/events/ src/tests/
git commit -m "🧹 [FIX] remove ArticleScrapedEvent shim and dead article_scraped.py"
```

---

## Task 2: `ArticleOutcome` enum

**Files:**
- Create: `src/modules/collection/application/article_outcome.py`
- Create: `src/tests/unit/test_article_outcome.py`

- [ ] **Step 1: Write the failing test**

Create `src/tests/unit/test_article_outcome.py`:
```python
def test_article_outcome_values():
    from src.modules.collection.application.article_outcome import ArticleOutcome
    assert ArticleOutcome.NEW.value == "new"
    assert ArticleOutcome.DUPLICATE.value == "duplicate"
    assert ArticleOutcome.FAILED.value == "failed"


def test_article_outcome_is_not_bool():
    from src.modules.collection.application.article_outcome import ArticleOutcome
    assert ArticleOutcome.NEW is not True
    assert ArticleOutcome.FAILED is not False
```

- [ ] **Step 2: Run to confirm failure**

```
docker compose run --rm test_service pytest src/tests/unit/test_article_outcome.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `src/modules/collection/application/article_outcome.py`:
```python
from enum import Enum


class ArticleOutcome(Enum):
    NEW = "new"
    DUPLICATE = "duplicate"
    FAILED = "failed"
```

- [ ] **Step 4: Run to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/test_article_outcome.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/modules/collection/application/article_outcome.py src/tests/unit/test_article_outcome.py
git commit -m "✨ [FEAT] add ArticleOutcome enum"
```

---

## Task 3: `PipelineStats` accumulator

**Files:**
- Create: `src/modules/collection/application/pipeline_stats.py`
- Create: `src/tests/unit/test_pipeline_stats.py`

- [ ] **Step 1: Write the failing tests**

Create `src/tests/unit/test_pipeline_stats.py`:
```python
from src.modules.collection.application.article_outcome import ArticleOutcome


def test_record_new_increments_new_count():
    from src.modules.collection.application.pipeline_stats import PipelineStats
    stats = PipelineStats()
    stats.record("arxiv", ArticleOutcome.NEW)
    stats.record("arxiv", ArticleOutcome.NEW)
    results = stats.get_results()
    assert len(results) == 1
    assert results[0].source == "arxiv"
    assert results[0].new == 2
    assert results[0].duplicate == 0
    assert results[0].failed == 0


def test_record_duplicate_increments_duplicate_count():
    from src.modules.collection.application.pipeline_stats import PipelineStats
    stats = PipelineStats()
    stats.record("rss", ArticleOutcome.DUPLICATE)
    results = stats.get_results()
    assert results[0].duplicate == 1
    assert results[0].new == 0


def test_record_failed_increments_failed_count():
    from src.modules.collection.application.pipeline_stats import PipelineStats
    stats = PipelineStats()
    stats.record("blog", ArticleOutcome.FAILED)
    results = stats.get_results()
    assert results[0].failed == 1


def test_multiple_sources_tracked_separately():
    from src.modules.collection.application.pipeline_stats import PipelineStats
    stats = PipelineStats()
    stats.record("arxiv", ArticleOutcome.NEW)
    stats.record("rss", ArticleOutcome.DUPLICATE)
    results = {r.source: r for r in stats.get_results()}
    assert results["arxiv"].new == 1
    assert results["rss"].duplicate == 1


def test_thread_safety_under_concurrent_writes():
    import threading
    from src.modules.collection.application.pipeline_stats import PipelineStats
    stats = PipelineStats()
    threads = [
        threading.Thread(target=stats.record, args=("arxiv", ArticleOutcome.NEW))
        for _ in range(100)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    results = stats.get_results()
    assert results[0].new == 100


def test_empty_stats_returns_empty_list():
    from src.modules.collection.application.pipeline_stats import PipelineStats
    stats = PipelineStats()
    assert stats.get_results() == []
```

- [ ] **Step 2: Run to confirm failure**

```
docker compose run --rm test_service pytest src/tests/unit/test_pipeline_stats.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `src/modules/collection/application/pipeline_stats.py`:
```python
import threading
from dataclasses import dataclass
from typing import List

from src.modules.collection.application.article_outcome import ArticleOutcome


@dataclass
class SourceStats:
    source: str
    new: int = 0
    duplicate: int = 0
    failed: int = 0


class PipelineStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sources: dict[str, SourceStats] = {}

    def record(self, source: str, outcome: ArticleOutcome) -> None:
        with self._lock:
            if source not in self._sources:
                self._sources[source] = SourceStats(source=source)
            s = self._sources[source]
            if outcome == ArticleOutcome.NEW:
                s.new += 1
            elif outcome == ArticleOutcome.DUPLICATE:
                s.duplicate += 1
            else:
                s.failed += 1

    def get_results(self) -> List[SourceStats]:
        with self._lock:
            return list(self._sources.values())
```

- [ ] **Step 4: Run to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/test_pipeline_stats.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/modules/collection/application/pipeline_stats.py src/tests/unit/test_pipeline_stats.py
git commit -m "✨ [FEAT] add PipelineStats accumulator"
```

---

## Task 4: `PipelineCompletedEvent`

**Files:**
- Create: `src/modules/collection/application/events/pipeline_completed.py`
- Modify: `src/modules/collection/application/events/__init__.py`

- [ ] **Step 1: Create the event dataclass**

Create `src/modules/collection/application/events/pipeline_completed.py`:
```python
from dataclasses import dataclass
from typing import List

from src.modules.collection.application.pipeline_stats import SourceStats


@dataclass(frozen=True)
class PipelineCompletedEvent:
    stats: List[SourceStats]
    duration_seconds: float
```

- [ ] **Step 2: Export from the events package**

Replace content of `src/modules/collection/application/events/__init__.py`:
```python
from .pipeline_completed import PipelineCompletedEvent

__all__ = ["PipelineCompletedEvent"]
```

- [ ] **Step 3: Verify importable**

```
docker compose run --rm test_service python -c "from src.modules.collection.application.events import PipelineCompletedEvent; print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add src/modules/collection/application/events/
git commit -m "✨ [FEAT] add PipelineCompletedEvent"
```

---

## Task 5: Update `ProcessScrapedArticleUseCase` to return `ArticleOutcome`

**Files:**
- Modify: `src/modules/collection/application/use_cases/process_scraped_article.py`
- Modify: `src/tests/integration/test_topic_article_pipeline.py`
- Modify: `src/tests/integration/test_arxiv_metadata.py`
- Modify: `src/tests/unit/test_process_article_topic_and_metadata.py`

- [ ] **Step 1: Update integration tests to assert `ArticleOutcome.NEW` instead of `True`**

In `src/tests/integration/test_topic_article_pipeline.py`, add the import at the top:
```python
from src.modules.collection.application.article_outcome import ArticleOutcome
```
Replace:
```python
result = uc.execute(event)
assert result is True
```
with:
```python
result = uc.execute(event)
assert result == ArticleOutcome.NEW
```

In `src/tests/integration/test_arxiv_metadata.py`, add the import at the top:
```python
from src.modules.collection.application.article_outcome import ArticleOutcome
```
Replace:
```python
result = uc.execute(scraped)
assert result is True
```
with:
```python
result = uc.execute(scraped)
assert result == ArticleOutcome.NEW
```

In `src/tests/unit/test_process_article_topic_and_metadata.py`, find any call to `uc.execute(...)` that asserts the return value and update similarly (if none, leave as-is).

- [ ] **Step 2: Run integration tests to confirm they fail (use case still returns `bool`)**

```
docker compose run --rm test_service pytest src/tests/integration/test_topic_article_pipeline.py src/tests/integration/test_arxiv_metadata.py -v
```
Expected: `AssertionError` — `ArticleOutcome.NEW != True`.

- [ ] **Step 3: Update the use case**

Replace the full content of `src/modules/collection/application/use_cases/process_scraped_article.py`:
```python
from typing import Optional

from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.shared.application.ports import EventBus
from src.shared.application.events import ArticleProcessedEvent
from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ArxivMetadata
from src.modules.collection.domain.repositories import ArxivMetadataRepository
from src.modules.collection.domain.services import DedupService
from src.modules.collection.domain.value_objects import UrlHash
from src.modules.collection.application.dtos import ScrapedArticleDTO
from src.modules.collection.application.article_outcome import ArticleOutcome

logger = get_logger(__name__)


class ProcessScrapedArticleUseCase:
    """
    Receives a ScrapedArticleDTO from infrastructure, applies dedup,
    persists a new Article (and ArxivMetadata when applicable), and publishes
    ArticleProcessedEvent for downstream contexts to consume.
    """

    def __init__(
        self,
        article_repo: ArticleRepository,
        dedup_service: DedupService,
        event_bus: EventBus,
        arxiv_metadata_repo: Optional[ArxivMetadataRepository] = None,
    ) -> None:
        self._article_repo = article_repo
        self._dedup_service = dedup_service
        self._event_bus = event_bus
        self._arxiv_metadata_repo = arxiv_metadata_repo

    def execute(self, dto: ScrapedArticleDTO) -> ArticleOutcome:
        existing = self._dedup_service.find_existing(dto.url)

        if existing is not None:
            if not self._dedup_service.needs_analysis(existing):
                logger.info("article_already_analyzed", url=dto.url)
                return ArticleOutcome.DUPLICATE
            if existing.source == "arxiv" and self._arxiv_metadata_repo is not None:
                stored = self._arxiv_metadata_repo.find_by_article_id(existing.id)
                if stored and stored.sections:
                    existing.metadata["sections"] = stored.sections
            logger.info("article_needs_analysis", article_id=str(existing.id))
            self._event_bus.publish(ArticleProcessedEvent(article=existing))
            return ArticleOutcome.DUPLICATE

        article = self._build_article(dto)

        try:
            saved = self._article_repo.save(article)
        except Exception as e:
            logger.error("article_save_failed", url=dto.url, error=str(e))
            return ArticleOutcome.FAILED

        if saved.source == "arxiv":
            self._save_arxiv_metadata(saved, dto.metadata)

        logger.info("article_saved", article_id=str(saved.id), url=dto.url)
        self._event_bus.publish(ArticleProcessedEvent(article=saved))
        return ArticleOutcome.NEW

    def _build_article(self, dto: ScrapedArticleDTO) -> Article:
        return Article(
            url=dto.url,
            url_hash=UrlHash.from_url(dto.url).value,
            source=dto.source,
            title=dto.title,
            content=dto.content,
            published_at=dto.published_at,
            topic_id=dto.topic_id,
            metadata=dto.metadata,
        )

    def _save_arxiv_metadata(self, article: Article, metadata: dict) -> None:
        if self._arxiv_metadata_repo is None:
            return
        entity = ArxivMetadata(
            article_id=article.id,
            arxiv_id=metadata.get("arxiv_id"),
            authors=metadata.get("authors") or [],
            pdf_available=bool(metadata.get("pdf_available", False)),
            sections=metadata.get("sections") or {},
        )
        try:
            self._arxiv_metadata_repo.save(entity)
        except Exception as e:
            logger.warning("arxiv_metadata_save_failed",
                           article_id=str(article.id), error=str(e))
```

- [ ] **Step 4: Run all tests to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/ src/tests/integration/ -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/modules/collection/application/use_cases/process_scraped_article.py \
        src/tests/integration/test_topic_article_pipeline.py \
        src/tests/integration/test_arxiv_metadata.py \
        src/tests/unit/test_process_article_topic_and_metadata.py
git commit -m "♻️ [FIX] ProcessScrapedArticleUseCase returns ArticleOutcome"
```

---

## Task 6: Update `ArticleScrapedHandler` to record outcomes

**Files:**
- Modify: `src/modules/collection/application/event_handlers/article_scraped_handler.py`
- Create: `src/tests/unit/test_article_scraped_handler.py`

- [ ] **Step 1: Write the failing tests**

Create `src/tests/unit/test_article_scraped_handler.py`:
```python
from unittest.mock import MagicMock
from src.modules.collection.application.article_outcome import ArticleOutcome
from src.modules.collection.application.pipeline_stats import PipelineStats
from src.modules.collection.application.dtos import ScrapedArticleDTO


def _make_dto(source="arxiv") -> ScrapedArticleDTO:
    return ScrapedArticleDTO(url="https://example.com", title="T", content="C", source=source)


def test_handle_new_article_records_new_and_returns_true():
    from src.modules.collection.application.event_handlers.article_scraped_handler import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = ArticleOutcome.NEW
    stats = PipelineStats()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats)
    result = handler.handle(_make_dto("arxiv"))

    assert result is True
    assert stats.get_results()[0].new == 1
    assert stats.get_results()[0].duplicate == 0


def test_handle_duplicate_article_records_duplicate_and_returns_true():
    from src.modules.collection.application.event_handlers.article_scraped_handler import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = ArticleOutcome.DUPLICATE
    stats = PipelineStats()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats)
    result = handler.handle(_make_dto("rss"))

    assert result is True
    assert stats.get_results()[0].duplicate == 1


def test_handle_failed_article_records_failed_and_returns_false():
    from src.modules.collection.application.event_handlers.article_scraped_handler import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = ArticleOutcome.FAILED
    stats = PipelineStats()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats)
    result = handler.handle(_make_dto("blog"))

    assert result is False
    assert stats.get_results()[0].failed == 1
```

- [ ] **Step 2: Run to confirm failure**

```
docker compose run --rm test_service pytest src/tests/unit/test_article_scraped_handler.py -v
```
Expected: `TypeError` — `ArticleScrapedHandler.__init__()` missing `pipeline_stats`.

- [ ] **Step 3: Update `ArticleScrapedHandler`**

Replace full content of `src/modules/collection/application/event_handlers/article_scraped_handler.py`:
```python
from src.modules.collection.application.dtos import ScrapedArticleDTO
from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
from src.modules.collection.application.pipeline_stats import PipelineStats
from src.modules.collection.application.article_outcome import ArticleOutcome


class ArticleScrapedHandler:
    def __init__(
        self,
        use_case: ProcessScrapedArticleUseCase,
        pipeline_stats: PipelineStats,
    ) -> None:
        self._use_case = use_case
        self._pipeline_stats = pipeline_stats

    def handle(self, dto: ScrapedArticleDTO) -> bool:
        outcome = self._use_case.execute(dto)
        self._pipeline_stats.record(dto.source, outcome)
        return outcome != ArticleOutcome.FAILED
```

- [ ] **Step 4: Run tests to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/test_article_scraped_handler.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/modules/collection/application/event_handlers/article_scraped_handler.py \
        src/tests/unit/test_article_scraped_handler.py
git commit -m "♻️ [FEAT] ArticleScrapedHandler records ArticleOutcome into PipelineStats"
```

---

## Task 7: Update `CollectionPipeline` to publish `PipelineCompletedEvent`

**Files:**
- Modify: `src/infrastructure/collection/collection_pipeline.py`
- Create: `src/tests/unit/test_collection_pipeline_stats.py`

- [ ] **Step 1: Write the failing test**

Create `src/tests/unit/test_collection_pipeline_stats.py`:
```python
from unittest.mock import MagicMock, patch
from src.modules.collection.application.article_outcome import ArticleOutcome
from src.modules.collection.application.pipeline_stats import PipelineStats
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.modules.collection.domain.value_objects import ScrapedArticle


def _make_setting(source="arxiv"):
    s = MagicMock()
    s.source = source
    s.id = "test-id"
    return s


def _make_scraper(articles):
    scraper = MagicMock()
    scraper.discover.return_value = [MagicMock(url=f"http://x.com/{i}") for i in range(len(articles))]
    scraper.fetch.side_effect = articles
    return scraper


def test_pipeline_publishes_pipeline_completed_event():
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline

    pipeline_stats = PipelineStats()
    event_bus = MagicMock()

    # simulate handler recording outcomes by having event_bus.publish side_effect
    def _fake_publish(event):
        if isinstance(event, PipelineCompletedEvent):
            return True
        # When ScrapedArticleDTO is published, simulate handler recording NEW
        pipeline_stats.record(event.source, ArticleOutcome.NEW)
        return True

    event_bus.publish.side_effect = _fake_publish

    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [_make_setting("arxiv")]

    scraper_factory = MagicMock()
    scraper = MagicMock()
    scraper.discover.return_value = [MagicMock(url="http://x.com/1")]
    article = MagicMock(spec=ScrapedArticle)
    article.url = "http://x.com/1"
    article.source = "arxiv"
    article.title = "T"
    article.content = "C"
    article.published_at = None
    article.topic_id = None
    article.authors = []
    article.extra = {}
    scraper.fetch.return_value = article
    scraper_factory.create_for.return_value = scraper

    executor = MagicMock()
    executor.run.side_effect = lambda tasks, on_result: on_result(article)

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        executor=executor,
    )
    pipeline.run()

    # verify PipelineCompletedEvent was published
    published_events = [
        call.args[0] for call in event_bus.publish.call_args_list
        if isinstance(call.args[0], PipelineCompletedEvent)
    ]
    assert len(published_events) == 1
    assert published_events[0].duration_seconds >= 0
```

- [ ] **Step 2: Run to confirm failure**

```
docker compose run --rm test_service pytest src/tests/unit/test_collection_pipeline_stats.py -v
```
Expected: `TypeError` — `CollectionPipeline.__init__()` unexpected keyword `pipeline_stats`.

- [ ] **Step 3: Update `CollectionPipeline`**

Replace full content of `src/infrastructure/collection/collection_pipeline.py`:
```python
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from src.infrastructure.collection.executor import FetchTask, ScrapeExecutor
from src.infrastructure.collection.scrapers import ConcreteScraperFactory
from src.shared.logging import get_logger
from src.modules.collection.domain.repositories import ScraperSettingRepository
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.modules.collection.application.dtos import ScrapedArticleDTO
from src.modules.collection.application.pipeline_stats import PipelineStats
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.shared.application.ports import EventBus

logger = get_logger(__name__)


class CollectionPipeline:
    def __init__(
        self,
        setting_repo: ScraperSettingRepository,
        scraper_factory: ConcreteScraperFactory,
        event_bus: EventBus,
        pipeline_stats: PipelineStats,
        executor: Optional[ScrapeExecutor] = None,
    ) -> None:
        self._setting_repo = setting_repo
        self._scraper_factory = scraper_factory
        self._event_bus = event_bus
        self._pipeline_stats = pipeline_stats
        self._executor = executor or ScrapeExecutor()

    def run(self) -> int:
        start = time.time()
        due_settings = self._setting_repo.get_active_due()

        if not due_settings:
            logger.info("no_sources_due")
            self._event_bus.publish(PipelineCompletedEvent(
                stats=[],
                duration_seconds=time.time() - start,
            ))
            return 0

        logger.info("sources_due", count=len(due_settings))

        # ── Phase 1: concurrent discover ──────────────────────────────────
        tasks: List[FetchTask] = []
        scraped_setting_ids = []

        def _discover(setting):
            scraper = self._scraper_factory.create_for(setting)
            return scraper, scraper.discover()

        with ThreadPoolExecutor(max_workers=len(due_settings)) as pool:
            futures = {pool.submit(_discover, s): s for s in due_settings}
            for future in as_completed(futures):
                setting = futures[future]
                try:
                    scraper, jobs = future.result()
                except Exception as e:
                    logger.error("discover_failed", source=setting.source, error=str(e))
                    continue

                logger.info("jobs_discovered", source=setting.source, count=len(jobs))
                for job in jobs:
                    tasks.append(FetchTask(
                        url=job.url,
                        source=setting.source,
                        job=job,
                        scraper=scraper,
                    ))
                scraped_setting_ids.append(setting.id)

        # ── Phase 2: concurrent fetch ─────────────────────────────────────
        results: List[ScrapedArticle] = []

        def on_result(article: ScrapedArticle) -> None:
            results.append(article)

        self._executor.run(tasks, on_result=on_result)

        # ── Phase 3: publish DTOs to event bus (triggers ArticleScrapedHandler) ─
        published = 0
        for article in results:
            dto = ScrapedArticleDTO.from_scraped_article(article)
            self._event_bus.publish(dto)
            published += 1

        # ── Mark settings scraped ─────────────────────────────────────────
        for setting_id in scraped_setting_ids:
            try:
                self._setting_repo.mark_scraped(setting_id)
            except Exception as e:
                logger.error("mark_scraped_failed", setting_id=str(setting_id), error=str(e))

        # ── Publish completion event (triggers Telegram + OTel) ───────────
        duration = time.time() - start
        self._event_bus.publish(PipelineCompletedEvent(
            stats=self._pipeline_stats.get_results(),
            duration_seconds=duration,
        ))

        logger.info("collection_pipeline_completed", published=published)
        return published
```

- [ ] **Step 4: Run tests to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/test_collection_pipeline_stats.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run the full test suite**

```
docker compose run --rm test_service pytest src/tests/unit/ -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/collection/collection_pipeline.py \
        src/tests/unit/test_collection_pipeline_stats.py
git commit -m "♻️ [FEAT] CollectionPipeline publishes PipelineCompletedEvent with stats"
```

---

## Task 8: Update `BaseNotifier` + `TelegramNotifier` interface

**Files:**
- Modify: `src/infrastructure/shared/notifications/base_notifier.py`
- Modify: `src/infrastructure/shared/notifications/telegram.py`
- Create: `src/tests/unit/test_telegram_notifier.py`

- [ ] **Step 1: Write the failing test**

Create `src/tests/unit/test_telegram_notifier.py`:
```python
from unittest.mock import patch, MagicMock
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.modules.collection.application.pipeline_stats import SourceStats


def _make_event(new=2, duplicate=1, failed=0, source="arxiv"):
    stats = [SourceStats(source=source, new=new, duplicate=duplicate, failed=failed)]
    return PipelineCompletedEvent(stats=stats, duration_seconds=12.5)


def test_notify_posts_to_telegram():
    from src.infrastructure.shared.notifications.telegram import TelegramNotifier
    event = _make_event()

    with patch("src.infrastructure.shared.notifications.telegram.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_post.return_value = mock_response

        notifier = TelegramNotifier(token="tok", chat_id="123")
        notifier.notify(event)

    assert mock_post.called
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["chat_id"] == "123"
    assert "parse_mode" in call_kwargs["json"]


def test_notify_message_contains_source_name():
    from src.infrastructure.shared.notifications.telegram import TelegramNotifier
    event = _make_event(source="my_rss_feed")

    with patch("src.infrastructure.shared.notifications.telegram.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_post.return_value = mock_response

        notifier = TelegramNotifier(token="tok", chat_id="123")
        notifier.notify(event)

    sent_text = mock_post.call_args.kwargs["json"]["text"]
    assert "my_rss_feed" in sent_text


def test_notify_with_empty_stats_sends_message():
    from src.infrastructure.shared.notifications.telegram import TelegramNotifier
    event = PipelineCompletedEvent(stats=[], duration_seconds=0.5)

    with patch("src.infrastructure.shared.notifications.telegram.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_post.return_value = mock_response

        notifier = TelegramNotifier(token="tok", chat_id="123")
        notifier.notify(event)

    assert mock_post.called
```

- [ ] **Step 2: Run to confirm failure**

```
docker compose run --rm test_service pytest src/tests/unit/test_telegram_notifier.py -v
```
Expected: `AttributeError` — `TelegramNotifier` has no `notify` method.

- [ ] **Step 3: Update `BaseNotifier`**

Replace full content of `src/infrastructure/shared/notifications/base_notifier.py`:
```python
from abc import ABC, abstractmethod

from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent


class BaseNotifier(ABC):
    @abstractmethod
    def notify(self, event: PipelineCompletedEvent) -> None: ...
```

- [ ] **Step 4: Update `TelegramNotifier`**

Replace full content of `src/infrastructure/shared/notifications/telegram.py`:
```python
import re
import requests
from datetime import datetime, timezone

from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from .base_notifier import BaseNotifier
from src.shared.logging import get_logger

logger = get_logger(__name__)


def _esc(s: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', s)


class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id

    def notify(self, event: PipelineCompletedEvent) -> None:
        text = self._format_message(event)
        response = requests.post(
            f"https://api.telegram.org/bot{self._token}/sendMessage",
            json={"chat_id": self._chat_id, "text": text, "parse_mode": "MarkdownV2"},
            timeout=10,
        )
        if not response.ok:
            logger.error(
                "telegram_send_failed",
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        response.raise_for_status()

    def _format_message(self, event: PipelineCompletedEvent) -> str:
        results = event.stats
        duration = event.duration_seconds
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        col_w = max((len(r.source) for r in results), default=10) + 2
        header = f"{'來源':<{col_w}} {'新增':>5} {'重複':>5} {'失敗':>5}"
        sep = "─" * (col_w + 19)
        rows = []
        for r in results:
            flag = " ⚠" if r.failed > 0 else ""
            rows.append(f"{r.source:<{col_w}} {r.new:>5} {r.duplicate:>5} {r.failed:>5}{flag}")

        total_new = sum(r.new for r in results)
        total_dup = sum(r.duplicate for r in results)
        total_failed = sum(r.failed for r in results)
        total_row = f"{'合計':<{col_w}} {total_new:>5} {total_dup:>5} {total_failed:>5}"
        table = "\n".join([header, sep] + rows + [sep, total_row])

        footer = (
            f"⚠ 有 {total_failed} 個錯誤，請檢查 log"
            if total_failed > 0
            else "✅ 全部完成"
        )

        plain = _esc(
            f"🤖 Scraping 任務完成\n\n"
            f"📅 {now}\n"
            f"⏱ 耗時：{duration:.1f} 秒\n"
            f"📦 來源數：{len(results)}"
        )

        return f"{plain}\n\n```\n{table}\n```\n\n{_esc(footer)}"
```

- [ ] **Step 5: Run tests to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/test_telegram_notifier.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Run full unit suite**

```
docker compose run --rm test_service pytest src/tests/unit/ -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/infrastructure/shared/notifications/base_notifier.py \
        src/infrastructure/shared/notifications/telegram.py \
        src/tests/unit/test_telegram_notifier.py
git commit -m "♻️ [FEAT] update BaseNotifier/TelegramNotifier to use PipelineCompletedEvent"
```

---

## Task 9: Refactor `NotificationHandler`

**Files:**
- Modify: `src/infrastructure/shared/notifications/notification_service.py`
- Modify: `src/infrastructure/shared/notifications/__init__.py`
- Create: `src/tests/unit/test_notification_handler.py`

- [ ] **Step 1: Write the failing tests**

Create `src/tests/unit/test_notification_handler.py`:
```python
from unittest.mock import MagicMock, patch
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.modules.collection.application.pipeline_stats import SourceStats


def _make_event():
    return PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=1, duplicate=0, failed=0)],
        duration_seconds=5.0,
    )


def test_handle_delegates_to_all_notifiers():
    from src.infrastructure.shared.notifications.notification_service import NotificationHandler
    n1 = MagicMock()
    n2 = MagicMock()
    handler = NotificationHandler(notifiers=[n1, n2])
    event = _make_event()
    handler.handle(event)
    n1.notify.assert_called_once_with(event)
    n2.notify.assert_called_once_with(event)


def test_handle_continues_if_one_notifier_raises():
    from src.infrastructure.shared.notifications.notification_service import NotificationHandler
    failing = MagicMock()
    failing.notify.side_effect = RuntimeError("network error")
    succeeding = MagicMock()
    handler = NotificationHandler(notifiers=[failing, succeeding])
    handler.handle(_make_event())
    succeeding.notify.assert_called_once()


def test_build_notification_handler_returns_handler():
    from src.infrastructure.shared.notifications.notification_service import build_notification_handler
    with patch.dict("os.environ", {}, clear=False):
        handler = build_notification_handler()
    from src.infrastructure.shared.notifications.notification_service import NotificationHandler
    assert isinstance(handler, NotificationHandler)
```

- [ ] **Step 2: Run to confirm failure**

```
docker compose run --rm test_service pytest src/tests/unit/test_notification_handler.py -v
```
Expected: `ImportError` — `NotificationHandler` not found.

- [ ] **Step 3: Refactor `notification_service.py`**

Replace full content of `src/infrastructure/shared/notifications/notification_service.py`:
```python
import os

from src.shared.logging import get_logger
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from .base_notifier import BaseNotifier
from .telegram import TelegramNotifier

logger = get_logger(__name__)


class NotificationHandler:
    def __init__(self, notifiers: list[BaseNotifier]) -> None:
        self._notifiers = notifiers

    def handle(self, event: PipelineCompletedEvent) -> None:
        for notifier in self._notifiers:
            try:
                notifier.notify(event)
            except Exception as e:
                logger.warning(
                    "notifier_failed",
                    notifier=type(notifier).__name__,
                    error=str(e),
                )


def build_notification_handler() -> NotificationHandler:
    notifiers: list[BaseNotifier] = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        notifiers.append(TelegramNotifier(token=token, chat_id=chat_id))
    else:
        missing = [
            k for k, v in {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}.items()
            if not v
        ]
        logger.warning("telegram_notifier_disabled", missing_env_vars=missing)
    return NotificationHandler(notifiers)
```

- [ ] **Step 4: Update `notifications/__init__.py`**

Replace full content of `src/infrastructure/shared/notifications/__init__.py`:
```python
from .notification_service import NotificationHandler, build_notification_handler
from .telegram import TelegramNotifier
from .base_notifier import BaseNotifier

__all__ = [
    "NotificationHandler",
    "build_notification_handler",
    "TelegramNotifier",
    "BaseNotifier",
]
```

- [ ] **Step 5: Run tests to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/test_notification_handler.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/shared/notifications/ \
        src/tests/unit/test_notification_handler.py
git commit -m "♻️ [FEAT] refactor notification_service to NotificationHandler class"
```

---

## Task 10: `OtelMetricsHandler`

**Files:**
- Create: `src/infrastructure/collection/handlers/__init__.py`
- Create: `src/infrastructure/collection/handlers/otel_metrics_handler.py`
- Create: `src/tests/unit/test_otel_metrics_handler.py`

- [ ] **Step 1: Write the failing test**

Create `src/tests/unit/test_otel_metrics_handler.py`:
```python
from unittest.mock import MagicMock, patch
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.modules.collection.application.pipeline_stats import SourceStats


def _make_event():
    return PipelineCompletedEvent(
        stats=[
            SourceStats(source="arxiv", new=3, duplicate=1, failed=0),
            SourceStats(source="rss", new=0, duplicate=0, failed=2),
        ],
        duration_seconds=8.0,
    )


def test_handler_fires_new_counter_per_source():
    from src.infrastructure.collection.handlers.otel_metrics_handler import OtelMetricsHandler

    mock_new = MagicMock()
    mock_dup = MagicMock()
    mock_err = MagicMock()

    with patch("src.infrastructure.collection.handlers.otel_metrics_handler.SCRAPER_ARTICLES_NEW", mock_new), \
         patch("src.infrastructure.collection.handlers.otel_metrics_handler.SCRAPER_ARTICLES_DUPLICATE", mock_dup), \
         patch("src.infrastructure.collection.handlers.otel_metrics_handler.SCRAPER_ERRORS", mock_err):

        OtelMetricsHandler().handle(_make_event())

    mock_new.add.assert_any_call(3, {"source": "arxiv"})
    mock_new.add.assert_any_call(0, {"source": "rss"})
    mock_dup.add.assert_any_call(1, {"source": "arxiv"})
    mock_err.add.assert_any_call(2, {"source": "rss"})
```

- [ ] **Step 2: Run to confirm failure**

```
docker compose run --rm test_service pytest src/tests/unit/test_otel_metrics_handler.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create the handler package and class**

Create `src/infrastructure/collection/handlers/__init__.py`:
```python
from .otel_metrics_handler import OtelMetricsHandler

__all__ = ["OtelMetricsHandler"]
```

Create `src/infrastructure/collection/handlers/otel_metrics_handler.py`:
```python
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.infrastructure.shared.observability.otel_metrics import (
    SCRAPER_ARTICLES_NEW,
    SCRAPER_ARTICLES_DUPLICATE,
    SCRAPER_ERRORS,
)


class OtelMetricsHandler:
    def handle(self, event: PipelineCompletedEvent) -> None:
        for s in event.stats:
            attrs = {"source": s.source}
            SCRAPER_ARTICLES_NEW.add(s.new, attrs)
            SCRAPER_ARTICLES_DUPLICATE.add(s.duplicate, attrs)
            SCRAPER_ERRORS.add(s.failed, attrs)
```

- [ ] **Step 4: Run test to confirm pass**

```
docker compose run --rm test_service pytest src/tests/unit/test_otel_metrics_handler.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/collection/handlers/ \
        src/tests/unit/test_otel_metrics_handler.py
git commit -m "✨ [FEAT] add OtelMetricsHandler for per-source article counters"
```

---

## Task 11: Wire `bootstrap.py` and clean `main.py`

**Files:**
- Modify: `src/bootstrap.py`
- Modify: `src/entrypoints/cli/main.py`

- [ ] **Step 1: Update `bootstrap.py`**

Add imports near the top of `build_collection_pipeline()`:
```python
from src.modules.collection.application.pipeline_stats import PipelineStats
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.infrastructure.collection.handlers import OtelMetricsHandler
from src.infrastructure.shared.notifications.notification_service import build_notification_handler
```

After the `DedupService` construction line, add:
```python
    pipeline_stats = PipelineStats()
```

Update `article_scraped_handler` construction:
```python
    article_scraped_handler = ArticleScrapedHandler(
        use_case=process_article_uc,
        pipeline_stats=pipeline_stats,
    )
```

Update `pipeline` construction:
```python
    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
    )
```

After the existing event handler subscriptions, add:
```python
    # Observability handlers — subscribe to PipelineCompletedEvent
    otel_handler = OtelMetricsHandler()
    event_bus.subscribe(PipelineCompletedEvent, otel_handler.handle)

    notification_handler = build_notification_handler()
    event_bus.subscribe(PipelineCompletedEvent, notification_handler.handle)
```

- [ ] **Step 2: Clean `main.py`**

Remove these lines from `src/entrypoints/cli/main.py`:
```python
from src.infrastructure.shared.observability import RunSummary   # line ~23
from src.infrastructure.shared.notifications import notify_all   # line ~24
```
and:
```python
    summary = RunSummary()   # line ~79
```
and:
```python
        notify_all(summary, duration)   # line ~103
```

`SCRAPER_RUNS` and `SCRAPER_DURATION` stay — they measure process lifecycle, not per-article outcomes.

- [ ] **Step 3: Run the full test suite**

```
docker compose run --rm test_service pytest src/tests/ -v
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/bootstrap.py src/entrypoints/cli/main.py
git commit -m "♻️ [FEAT] wire PipelineStats and observability handlers in bootstrap"
```

---

## Task 12: Delete `run_summary.py` and clean observability exports

**Files:**
- Delete: `src/infrastructure/shared/observability/run_summary.py`
- Modify: `src/infrastructure/shared/observability/__init__.py`

- [ ] **Step 1: Verify nothing imports `RunSummary` or `SourceResult` anymore**

```bash
grep -r "RunSummary\|SourceResult" src/ --include="*.py"
```
Expected: no results (only the definition files themselves, which we're about to delete).

- [ ] **Step 2: Remove exports from observability `__init__.py`**

In `src/infrastructure/shared/observability/__init__.py`, remove:
```python
from .run_summary import RunSummary, SourceResult
```
and remove `"RunSummary"` and `"SourceResult"` from `__all__`.

- [ ] **Step 3: Delete the file**

```bash
rm src/infrastructure/shared/observability/run_summary.py
```

- [ ] **Step 4: Run the full test suite one final time**

```
docker compose run --rm test_service pytest src/tests/ -v
```
Expected: all pass.

- [ ] **Step 5: Final commit**

```bash
git add src/infrastructure/shared/observability/
git commit -m "🧹 [FIX] delete run_summary.py — replaced by PipelineStats"
```
