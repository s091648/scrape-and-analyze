# Contract: CLI Job Completion Notification Events

Extends the existing `main.py` pattern (`PipelineCompletedEvent` → `NotificationHandler` → `*MessageBuilder` → `TelegramNotifierClient`) to `refresh_metrics.py` and `backfill_rag.py`. See data-model.md for the two new event dataclasses' field shapes and research.md for why this pattern (not `weekly_report.py`'s embedded-per-item notification) is the right one to copy.

## Wiring shape (per entrypoint, mirrors `main.py`)

```python
# inside build_metrics_refresh_pipeline() / build_rag_backfill_pipeline() in src/bootstrap.py
event_bus = InMemoryEventBus()
notification_handler = build_notification_handler(MetricsRefreshMessageBuilder)  # or RagBackfillMessageBuilder
event_bus.subscribe(MetricsRefreshCompletedEvent, notification_handler.handle)
# ... return event_bus alongside the existing service/repo/session tuple
```

```python
# inside refresh_metrics.py's main(), after computing refreshed/failed (existing code, unchanged)
event_bus.publish(MetricsRefreshCompletedEvent(
    total=len(rows), refreshed=refreshed, failed=failed,
    duration_seconds=time.time() - start_time,
))
```

## Required change: `build_notification_handler()` becomes message-builder-parameterized

Current signature (`src/infrastructure/shared/notifications/notification_service.py`):

```python
def build_notification_handler() -> NotificationHandler:
    ...
    def sender(event: PipelineCompletedEvent) -> None:
        message = PipelineCompletedMessageBuilder.build(event)
        ...
```

`PipelineCompletedMessageBuilder` is hardcoded inside the closure. To reuse this function for the two new jobs without copy-pasting the Telegram-client/env-var wiring, it takes the message builder as a parameter:

```python
def build_notification_handler(message_builder) -> NotificationHandler:
    ...
    def sender(event) -> None:
        message = message_builder.build(event)
        ...
```

`main.py`'s existing call site becomes `build_notification_handler(PipelineCompletedMessageBuilder)` — a mechanical, behavior-preserving change (verified by the existing `test_notification_build.py` continuing to pass unmodified).

## `NotificationHandler` type-hint widening

`NotificationHandler.__init__`/`handle` currently type-hint `Callable[[PipelineCompletedEvent], None]` / `event: PipelineCompletedEvent`. Widened to `Callable[[Any], None]` / `event: Any` — a type-hint-only change (Python does not enforce this at runtime; `sender(event)` and the `try/except` fan-out logic in `handle()` are already fully generic). No behavior change for the existing `main.py` call site.

## Message builders (new, one per event, mirroring `PipelineCompletedMessageBuilder`)

- `src/infrastructure/collection/notifications/metrics_refresh_message_builder.py::MetricsRefreshMessageBuilder.build(event: MetricsRefreshCompletedEvent) -> TelegramMessage`
- `src/infrastructure/intelligence/notifications/rag_backfill_message_builder.py::RagBackfillMessageBuilder.build(event: RagBackfillCompletedEvent) -> TelegramMessage`

Both follow the same MarkdownV2-escaping (`_esc`) and "✅ 全部完成" / "⚠ 有 N 個錯誤，請檢查 log" footer convention as `PipelineCompletedMessageBuilder`, adapted to a flat total/success/failed summary instead of a per-source table.

## Failure isolation (FR-012)

`NotificationHandler.handle()` already wraps each sender call in its own `try/except`, logging and continuing rather than propagating (existing behavior, unchanged). Because `event_bus.publish(...)` is called from `main()` *after* the job's own data-changing work has already completed and been committed, a notification failure — whether inside the sender or a total publish failure — cannot roll back or otherwise affect the job's already-persisted results.
