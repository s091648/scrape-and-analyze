"""Tests for NotificationHandler dispatching pipeline events to sender callables."""
from unittest.mock import MagicMock

from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats


def _make_event():
    return PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=1, duplicate=0, failed=0)],
        duration_seconds=5.0,
    )


def test_handle_delegates_to_all_senders():
    from src.infrastructure.shared.notifications.notification_service import NotificationHandler
    s1 = MagicMock()
    s2 = MagicMock()
    handler = NotificationHandler(senders=[s1, s2])
    event = _make_event()
    handler.handle(event)
    s1.assert_called_once_with(event)
    s2.assert_called_once_with(event)


def test_handle_continues_if_one_sender_raises():
    from src.infrastructure.shared.notifications.notification_service import NotificationHandler
    failing = MagicMock(side_effect=RuntimeError("network error"))
    succeeding = MagicMock()
    handler = NotificationHandler(senders=[failing, succeeding])
    handler.handle(_make_event())
    succeeding.assert_called_once()


def test_build_notification_handler_returns_handler():
    from src.infrastructure.shared.notifications.notification_service import (
        NotificationHandler,
        build_notification_handler,
    )
    handler = build_notification_handler()
    assert isinstance(handler, NotificationHandler)
