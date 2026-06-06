from unittest.mock import patch, MagicMock
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats


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


def test_notify_posts_to_correct_url():
    """POST URL must match https://api.telegram.org/bot{token}/sendMessage."""
    from src.infrastructure.shared.notifications.telegram import TelegramNotifier
    event = _make_event()
    with patch("src.infrastructure.shared.notifications.telegram.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_post.return_value = mock_response
        notifier = TelegramNotifier(token="mytoken", chat_id="999")
        notifier.notify(event)
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.telegram.org/botmytoken/sendMessage"


def test_notify_sends_markdownv2():
    """POST payload must include parse_mode='MarkdownV2'."""
    from src.infrastructure.shared.notifications.telegram import TelegramNotifier
    event = _make_event()
    with patch("src.infrastructure.shared.notifications.telegram.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_post.return_value = mock_response
        notifier = TelegramNotifier(token="tok", chat_id="123")
        notifier.notify(event)
    assert mock_post.call_args.kwargs["json"]["parse_mode"] == "MarkdownV2"
