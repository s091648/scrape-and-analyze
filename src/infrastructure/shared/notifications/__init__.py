"""Cross-module notification transport only.

This package holds transport clients genuinely shared across modules (e.g.
TelegramNotifierClient) — mirrors the persistence/{shared,collection,intelligence}
split, where `shared` means "used by more than one module," not "notification-related."

Per-event/per-entity message content (what a notification says) belongs to the
module that owns that event or entity, under infrastructure/<module>/notifications/
— e.g. PipelineCompletedMessageBuilder under infrastructure/collection/notifications/
(formats collection's PipelineCompletedEvent), or WeeklyReportTelegramMessageBuilder
under infrastructure/intelligence/notifications/ (formats intelligence's WeeklyReport).
"""
from .notification_service import (
    NotificationHandler, build_notification_handler,
    AsyncNotificationHandler, build_async_notification_handler,
)
from .telegram_notifier_client import TelegramNotifierClient


__all__ = [
    "NotificationHandler",
    "build_notification_handler",
    "AsyncNotificationHandler",
    "build_async_notification_handler",
    "TelegramNotifierClient",
]
