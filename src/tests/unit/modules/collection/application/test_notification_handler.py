from unittest.mock import MagicMock, patch
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats


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