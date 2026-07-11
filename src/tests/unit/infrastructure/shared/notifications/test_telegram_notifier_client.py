"""Tests for the shared TelegramNotifierClient (HTTP transport)."""
from unittest.mock import MagicMock, patch

import pytest


def _mock_response(ok=True, status_code=200, body="ok"):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.text = body
    if not ok:
        import requests
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code} error")
    return resp


def test_constructor_requires_bot_token():
    from src.shared.infrastructure.notifications import TelegramNotifierClient

    with pytest.raises(ValueError):
        TelegramNotifierClient(bot_token="")


def test_send_posts_to_correct_url():
    from src.shared.infrastructure.notifications import TelegramNotifierClient

    with patch(
        "src.shared.infrastructure.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = _mock_response()
        notifier = TelegramNotifierClient(bot_token="mytoken")
        from src.shared.domain.value_objects.telegram_message import TelegramMessage
        notifier.send("999", TelegramMessage(text="hi", parse_mode="Markdown"))

    assert mock_post.call_args.args[0] == "https://api.telegram.org/botmytoken/sendMessage"


def test_send_payload_includes_chat_id_text_and_parse_mode():
    from src.shared.infrastructure.notifications import TelegramNotifierClient
    from src.shared.domain.value_objects.telegram_message import TelegramMessage

    with patch(
        "src.shared.infrastructure.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = _mock_response()
        notifier = TelegramNotifierClient(bot_token="tok")
        notifier.send("123", TelegramMessage(text="hello *world*", parse_mode="MarkdownV2"))

    payload = mock_post.call_args.kwargs["json"]
    assert payload["chat_id"] == "123"
    assert payload["text"] == "hello *world*"
    assert payload["parse_mode"] == "MarkdownV2"


def test_send_uses_send_photo_when_photo_url_set():
    from src.shared.infrastructure.notifications import TelegramNotifierClient
    from src.shared.domain.value_objects.telegram_message import TelegramMessage

    with patch(
        "src.shared.infrastructure.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = _mock_response()
        notifier = TelegramNotifierClient(bot_token="tok")
        notifier.send("123", TelegramMessage(text="hi", photo_url="https://cdn.example.com/x.png"))

    assert mock_post.call_args.args[0] == "https://api.telegram.org/bottok/sendPhoto"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["photo"] == "https://cdn.example.com/x.png"
    assert payload["caption"] == "hi"


def test_send_truncates_long_caption_for_send_photo():
    from src.shared.infrastructure.notifications import TelegramNotifierClient
    from src.shared.domain.value_objects.telegram_message import TelegramMessage

    with patch(
        "src.shared.infrastructure.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = _mock_response()
        notifier = TelegramNotifierClient(bot_token="tok")
        notifier.send("123", TelegramMessage(text="A" * 2000, photo_url="https://cdn.example.com/x.png"))

    payload = mock_post.call_args.kwargs["json"]
    assert len(payload["caption"]) == 1024


def test_send_raises_on_non_ok_response():
    from src.shared.infrastructure.notifications import TelegramNotifierClient
    from src.shared.domain.value_objects.telegram_message import TelegramMessage

    with patch(
        "src.shared.infrastructure.notifications.telegram_notifier_client.requests.post"
    ) as mock_post:
        mock_post.return_value = _mock_response(ok=False, status_code=400, body="bad request")
        notifier = TelegramNotifierClient(bot_token="tok")
        with pytest.raises(Exception):
            notifier.send("123", TelegramMessage(text="hi"))
