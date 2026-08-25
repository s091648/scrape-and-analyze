"""Job completion notification dispatch.

NotificationHandler fans a completion event (PipelineCompletedEvent and, since
020-redis-caching-layer, MetricsRefreshCompletedEvent / RagBackfillCompletedEvent) out to
a list of sender callables. Each sender is a thin closure built by
build_notification_handler() that wires a content builder + transport (Telegram client)
for a target chat.

This module owns no Telegram-specific formatting — that's the job of the per-event
message builder (e.g. PipelineCompletedMessageBuilder) passed into build_notification_handler().
"""
from typing import Any, Callable

from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer
from src.shared.logging import get_logger

logger = get_logger(__name__)


class NotificationHandler:
    """Dispatches job completion events to all registered sender callables.

    Event-agnostic — usable for any completion event shape, as long as the message
    builder passed to build_notification_handler() knows how to render it."""
    def __init__(self, senders: list[Callable[[Any], None]]) -> None:
        self._senders = senders

    def handle(self, event: Any) -> None:
        """Fan out the event to every sender, swallowing individual failures."""
        for sender in self._senders:
            try:
                sender(event)
            except Exception as e:
                logger.warning(
                    "notifier_failed",
                    sender=getattr(sender, "__name__", type(sender).__name__),
                    error=str(e),
                )


def build_notification_handler(message_builder=None) -> NotificationHandler:
    """Build a NotificationHandler with a Telegram sender if env vars are configured.

    `message_builder` must expose `build(event) -> TelegramMessage`; defaults to
    PipelineCompletedMessageBuilder for backward compatibility with the main scrape
    pipeline's existing call site. Returns a handler with an empty senders list (and a
    warning log) when TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is unset.
    """
    from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from src.infrastructure.shared.notifications.telegram_notifier_client import TelegramNotifierClient
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    if message_builder is None:
        message_builder = PipelineCompletedMessageBuilder

    senders: list[Callable[[Any], None]] = []
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    if token and chat_id:
        notifier = TelegramNotifierClient(bot_token=token)

        def sender(event: Any) -> None:
            message = message_builder.build(event)
            notifier.send(chat_id, message)

        senders.append(sender)
    else:
        missing = [
            k for k, v in {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}.items()
            if not v
        ]
        logger.warning("telegram_notifier_disabled", missing_env_vars=missing)
    return NotificationHandler(senders)


class AsyncNotificationHandler:
    """024-async-pipeline-refactor: async sibling of NotificationHandler — new,
    separate class. NotificationHandler/build_notification_handler() are
    shared across five pipelines (collection, weekly-report, metrics-refresh,
    dedup-reconciliation, RAG-backfill), only the first of which is in scope
    — converting NotificationHandler.handle() to async in place would silently
    break the other four's sync EventBus.subscribe(...).handle calls. Senders
    themselves stay synchronous (a single end-of-run Telegram call is not part
    of any per-article concurrent path) — only the dispatch loop is async, to
    satisfy the EventBus Protocol."""

    def __init__(self, senders: list[Callable[[Any], None]]) -> None:
        self._senders = senders

    async def handle(self, event: Any) -> None:
        """Fan out the event to every sender, swallowing individual failures."""
        with get_tracer().start_as_current_span(SpanName.PIPELINE_COMPLETED_NOTIFY) as span:
            span.set_attribute("notify.senders_count", len(self._senders))
            failed_count = 0
            for sender in self._senders:
                try:
                    sender(event)
                except Exception as e:
                    failed_count += 1
                    logger.warning(
                        "notifier_failed",
                        sender=getattr(sender, "__name__", type(sender).__name__),
                        error=str(e),
                    )
            span.set_attribute("notify.failed_count", failed_count)


def build_async_notification_handler(message_builder=None) -> AsyncNotificationHandler:
    """Async sibling of build_notification_handler() — same config-loading
    logic, returns an AsyncNotificationHandler instead."""
    from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from src.infrastructure.shared.notifications.telegram_notifier_client import TelegramNotifierClient
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    if message_builder is None:
        message_builder = PipelineCompletedMessageBuilder

    senders: list[Callable[[Any], None]] = []
    token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    if token and chat_id:
        notifier = TelegramNotifierClient(bot_token=token)

        def sender(event: Any) -> None:
            message = message_builder.build(event)
            notifier.send(chat_id, message)

        senders.append(sender)
    else:
        missing = [
            k for k, v in {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id}.items()
            if not v
        ]
        logger.warning("telegram_notifier_disabled", missing_env_vars=missing)
    return AsyncNotificationHandler(senders)
