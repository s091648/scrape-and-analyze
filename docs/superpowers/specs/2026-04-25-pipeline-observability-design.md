# Pipeline Observability Wiring — Design Spec

**Date:** 2026-04-25
**Branch:** feat/clean_architecture

---

## Problem

Four distinct issues, all rooted in the same cause — observability signals never reach the pipeline:

1. **Empty Telegram notifications.** `RunSummary` is created in `main.py` but never passed to the pipeline; `record_new/duplicate/failed()` are never called; the notification always renders a blank table.
2. **Dead OTel counters.** `SCRAPER_ARTICLES_NEW`, `SCRAPER_ARTICLES_DUPLICATE`, `SCRAPER_ERRORS` are defined in `otel_metrics.py` but never called anywhere.
3. **Dead code / shim confusion.** `collection/application/events/article_scraped.py` defines `ArticleScrapedEvent` as a frozen dataclass, but `__init__.py` shadows it with a shim re-exporting `ScrapedArticleDTO as ArticleScrapedEvent`. The original class is unreachable. Six test files use the deprecated alias.
4. **Wrong layer for `RunSummary`.** It lives in `infrastructure/shared/observability/` alongside OTel config, but its only purpose is to accumulate per-run article stats — an application-level concern.

---

## Goals

- Telegram notification shows correct per-source `new / duplicate / failed` counts.
- `SCRAPER_ARTICLES_NEW`, `SCRAPER_ARTICLES_DUPLICATE`, `SCRAPER_ERRORS` OTel counters are populated.
- Dead `article_scraped.py` and its shim are removed; tests import `ScrapedArticleDTO` directly.
- Stats accumulation lives in `collection/application/`, not in infrastructure observability.
- `main.py` is not aware of per-article outcomes; it only manages process lifecycle.

### Out of scope

- Adding child OTel spans inside `CollectionPipeline` / `ScrapeExecutor` / scrapers.
- Fixing `SCRAPER_ARTICLES_FOUND` inconsistency (only `arxiv_scraper.py` calls it; RSS/blog don't).
- Changing the `InMemoryEventBus` protocol.

---

## Architecture

### Core idea

`CollectionPipeline` gains a `PipelineStats` accumulator. The handler that processes each scraped article (`ArticleScrapedHandler`) updates it based on the use case outcome. When `run()` finishes, the pipeline publishes a `PipelineCompletedEvent` carrying the aggregated stats. Infrastructure handlers subscribed to that event send the Telegram notification and fire OTel counters.

```
bootstrap.py
  creates PipelineStats()
  injects into ArticleScrapedHandler + CollectionPipeline

CollectionPipeline.run()
  Phase 3: event_bus.publish(ScrapedArticleDTO) per article
    └── ArticleScrapedHandler.handle(dto)
          ├── ProcessScrapedArticleUseCase.execute(dto) → ArticleOutcome
          └── pipeline_stats.record(source, outcome)
  Phase end: event_bus.publish(PipelineCompletedEvent(stats, duration_seconds))
    ├── TelegramNotifyHandler.handle(event)
    └── OtelMetricsHandler.handle(event)
```

### Layer assignments

| Concept | Layer | Path |
|---|---|---|
| `ArticleOutcome` enum | collection application | `src/modules/collection/application/article_outcome.py` |
| `SourceStats`, `PipelineStats` | collection application | `src/modules/collection/application/pipeline_stats.py` |
| `PipelineCompletedEvent` | collection application events | `src/modules/collection/application/events/pipeline_completed.py` |
| `TelegramNotifyHandler` | collection infrastructure handlers | `src/infrastructure/collection/handlers/telegram_notify_handler.py` |
| `OtelMetricsHandler` | collection infrastructure handlers | `src/infrastructure/collection/handlers/otel_metrics_handler.py` |

---

## Component Designs

### `ArticleOutcome`

```python
# src/modules/collection/application/article_outcome.py
from enum import Enum

class ArticleOutcome(Enum):
    NEW = "new"
    DUPLICATE = "duplicate"
    FAILED = "failed"
```

`ProcessScrapedArticleUseCase.execute()` currently returns `bool`. It changes to return `ArticleOutcome`:

- New article saved → `ArticleOutcome.NEW`
- Duplicate, already analyzed (skipped) → `ArticleOutcome.DUPLICATE`
- Duplicate, needs re-analysis (re-queued) → `ArticleOutcome.DUPLICATE`
- Any exception during save or publish → `ArticleOutcome.FAILED`

`ArticleScrapedHandler.handle()` returns `ArticleOutcome` (propagated from use case). The `EventBus.publish()` protocol is **not changed** — its `bool` return value is not used for stats collection.

### `PipelineStats`

Replaces `RunSummary` from `infrastructure/shared/observability/run_summary.py`. Thread-safe, same `threading.Lock` approach.

```python
# src/modules/collection/application/pipeline_stats.py
import threading
from dataclasses import dataclass
from typing import List
from .article_outcome import ArticleOutcome

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
            stats = self._sources[source]
            if outcome == ArticleOutcome.NEW:
                stats.new += 1
            elif outcome == ArticleOutcome.DUPLICATE:
                stats.duplicate += 1
            else:
                stats.failed += 1

    def get_results(self) -> List[SourceStats]:
        with self._lock:
            return list(self._sources.values())
```

### `PipelineCompletedEvent`

```python
# src/modules/collection/application/events/pipeline_completed.py
from dataclasses import dataclass
from typing import List
from src.modules.collection.application.pipeline_stats import SourceStats

@dataclass(frozen=True)
class PipelineCompletedEvent:
    stats: List[SourceStats]  # list itself is not replaced after publish; elements are not mutated
    duration_seconds: float
```

Published by `CollectionPipeline.run()` at the end of every execution (including runs where `due_settings` is empty — it publishes with empty stats and the no-op duration). `frozen=True` prevents re-assignment of the event's fields; the `SourceStats` elements inside `stats` are treated as read-only by convention after publish.

### `CollectionPipeline` changes

Constructor gains `pipeline_stats: PipelineStats`. At end of `run()`:

```python
import time
# at start of run():
start = time.time()

# after mark_scraped loop:
duration = time.time() - start
self._event_bus.publish(PipelineCompletedEvent(
    stats=self._pipeline_stats.get_results(),
    duration_seconds=duration,
))
```

### `ArticleScrapedHandler` changes

Constructor gains `pipeline_stats: PipelineStats`. The handler keeps returning `bool` for event bus compatibility (`InMemoryEventBus` only recognises explicit `False` as failure). Stats recording is a side-effect:

```python
def handle(self, dto: ScrapedArticleDTO) -> bool:
    outcome = self._use_case.execute(dto)
    self._pipeline_stats.record(dto.source, outcome)
    return outcome != ArticleOutcome.FAILED
```

### `BaseNotifier` interface update

`BaseNotifier` currently depends on `RunSummary`. Change the interface to accept `PipelineCompletedEvent` directly — the event already carries both stats and duration, so no separate `duration` argument is needed:

```python
# src/infrastructure/shared/notifications/base_notifier.py
from abc import ABC, abstractmethod
from src.modules.collection.application.events import PipelineCompletedEvent

class BaseNotifier(ABC):
    @abstractmethod
    def notify(self, event: PipelineCompletedEvent) -> None: ...
```

`TelegramNotifier.send_scrape_summary(summary, duration)` is renamed to `notify(event)` and its formatting logic reads `event.stats` and `event.duration_seconds`.

### `NotificationHandler`

`notification_service.py` is refactored in-place into a `NotificationHandler` class. It replaces the module-level `notify_all()` function with an event-handler-compatible `handle()` method, and registers itself on the event bus via bootstrap. Adding a new notifier (e.g. Slack) in future means only implementing `BaseNotifier` and registering it in `get_notifiers()`.

```python
# src/infrastructure/shared/notifications/notification_service.py
class NotificationHandler:
    def __init__(self, notifiers: list[BaseNotifier]) -> None:
        self._notifiers = notifiers

    def handle(self, event: PipelineCompletedEvent) -> None:
        for notifier in self._notifiers:
            try:
                notifier.notify(event)
            except Exception as e:
                logger.warning("notifier_failed", notifier=type(notifier).__name__, error=str(e))


def build_notification_handler() -> NotificationHandler:
    """Reads env vars and constructs the configured notifiers."""
    notifiers: list[BaseNotifier] = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        notifiers.append(TelegramNotifier(token=token, chat_id=chat_id))
    return NotificationHandler(notifiers)
```

Bootstrap subscribes `NotificationHandler.handle` to `PipelineCompletedEvent`.

### `OtelMetricsHandler`

New infrastructure handler:

```python
# src/infrastructure/collection/handlers/otel_metrics_handler.py
class OtelMetricsHandler:
    def handle(self, event: PipelineCompletedEvent) -> None:
        for s in event.stats:
            attrs = {"source": s.source}
            SCRAPER_ARTICLES_NEW.add(s.new, attrs)
            SCRAPER_ARTICLES_DUPLICATE.add(s.duplicate, attrs)
            SCRAPER_ERRORS.add(s.failed, attrs)
```

### `bootstrap.py` changes

```python
from src.modules.collection.application.pipeline_stats import PipelineStats
from src.modules.collection.application.events import PipelineCompletedEvent
from src.infrastructure.collection.handlers import OtelMetricsHandler
from src.infrastructure.shared.notifications.notification_service import build_notification_handler

pipeline_stats = PipelineStats()

article_scraped_handler = ArticleScrapedHandler(
    use_case=process_article_uc,
    pipeline_stats=pipeline_stats,
)

pipeline = CollectionPipeline(
    setting_repo=setting_repo,
    scraper_factory=scraper_factory,
    event_bus=event_bus,
    pipeline_stats=pipeline_stats,
)

# Observability handlers
otel_handler = OtelMetricsHandler()
event_bus.subscribe(PipelineCompletedEvent, otel_handler.handle)

notification_handler = build_notification_handler()
event_bus.subscribe(PipelineCompletedEvent, notification_handler.handle)
```

### `main.py` changes

Remove:
- `from src.infrastructure.shared.observability import RunSummary`
- `summary = RunSummary()`
- `notify_all(summary, duration)`
- `from src.infrastructure.shared.notifications import notify_all`

`SCRAPER_RUNS` and `SCRAPER_DURATION` stay in `main.py` — they measure process-level lifecycle, not per-article outcomes.

---

## Files Changed

### New files

| File | Purpose |
|---|---|
| `src/modules/collection/application/article_outcome.py` | `ArticleOutcome` enum |
| `src/modules/collection/application/pipeline_stats.py` | `SourceStats`, `PipelineStats` accumulator |
| `src/modules/collection/application/events/pipeline_completed.py` | `PipelineCompletedEvent` |
| `src/infrastructure/collection/handlers/__init__.py` | exports |
| `src/infrastructure/collection/handlers/otel_metrics_handler.py` | OTel metrics infra handler |

### Modified files

| File | Change |
|---|---|
| `src/modules/collection/application/use_cases/process_scraped_article.py` | returns `ArticleOutcome` instead of `bool` |
| `src/modules/collection/application/event_handlers/article_scraped_handler.py` | receives `PipelineStats`, records outcome |
| `src/infrastructure/collection/collection_pipeline.py` | receives `PipelineStats`, publishes `PipelineCompletedEvent` |
| `src/bootstrap.py` | wires `PipelineStats`, new handlers |
| `src/entrypoints/cli/main.py` | remove `RunSummary`, `notify_all` |
| `src/modules/collection/application/events/__init__.py` | remove shim, export `PipelineCompletedEvent` |
| `src/infrastructure/shared/observability/__init__.py` | remove `RunSummary` export |
| `src/infrastructure/shared/notifications/base_notifier.py` | interface: `send_scrape_summary(RunSummary, float)` → `notify(PipelineCompletedEvent)` |
| `src/infrastructure/shared/notifications/telegram.py` | implement new `notify(event)` interface |
| `src/infrastructure/shared/notifications/notification_service.py` | refactor to `NotificationHandler` class + `build_notification_handler()` factory |
| `src/infrastructure/shared/notifications/__init__.py` | update exports |
| 6 test files importing `ArticleScrapedEvent` | replace with `ScrapedArticleDTO` |

### Deleted files

| File | Reason |
|---|---|
| `src/modules/collection/application/events/article_scraped.py` | unreachable dead class |
| `src/infrastructure/shared/observability/run_summary.py` | replaced by `PipelineStats` |

---

## Testing

### Unit tests (new)

- `test_article_outcome.py` — enum values
- `test_pipeline_stats.py` — `record()` increments correctly per outcome; thread-safety under concurrent writes
- `test_notification_handler.py` — `NotificationHandler.handle()` delegates to all registered notifiers; exceptions in one notifier don't abort others
- `test_telegram_notifier.py` — formats message from `PipelineCompletedEvent`; HTTP call with correct payload
- `test_otel_metrics_handler.py` — calls correct counters with correct per-source attributes

### Unit tests (updated)

- `test_process_scraped_article.py` — assert `ArticleOutcome.NEW` / `ArticleOutcome.DUPLICATE` / `ArticleOutcome.FAILED`
- `test_article_scraped_handler.py` — verify `pipeline_stats.record()` is called with correct source + outcome

### Integration tests (updated)

- Replace `ArticleScrapedEvent` → `ScrapedArticleDTO` in 6 test files:
  - `test_topic_article_pipeline.py`
  - `test_topic_id_propagation.py`
  - `test_scrape_task.py`
  - `test_arxiv_metadata.py`
  - `test_scrapers.py`
  - `test_process_article_topic_and_metadata.py`

### Integration test (new)

- `test_collection_pipeline_stats.py` — run pipeline with mock scraper returning 2 new + 1 duplicate; assert `PipelineCompletedEvent` stats match; assert Telegram handler received event.

---

## Migration Notes

The shim in `collection/application/events/__init__.py` is safe to remove immediately — all six consumers are test files and will be updated in the same PR. No production code imports `ArticleScrapedEvent`.
