from unittest.mock import patch, MagicMock
from src.infrastructure.observability.run_summary import RunSummary
from src.notifications.telegram import TelegramNotifier


def _make_summary():
    s = RunSummary()
    s.record_new("techcrunch")
    s.record_new("techcrunch")
    s.record_duplicate("venturebeat")
    s.record_failed("arxiv")
    return s


def test_telegram_notifier_calls_api():
    notifier = TelegramNotifier(token="fake_token", chat_id="12345")
    summary = _make_summary()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_response) as mock_post:
        notifier.send_scrape_summary(summary, duration=42.5)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "https://api.telegram.org/botfake_token/sendMessage" in call_kwargs[0][0]
    payload = call_kwargs[1]["json"]
    assert payload["chat_id"] == "12345"
    assert "Scraping" in payload["text"]


def test_message_contains_source_names():
    notifier = TelegramNotifier(token="t", chat_id="1")
    summary = _make_summary()

    with patch("requests.post") as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()
        notifier.send_scrape_summary(summary, duration=10.0)

    text = mock_post.call_args[1]["json"]["text"]
    assert "techcrunch" in text
    assert "venturebeat" in text
    assert "arxiv" in text


def test_message_contains_error_warning_when_failures():
    notifier = TelegramNotifier(token="t", chat_id="1")
    summary = _make_summary()  # has 1 failed (arxiv)

    with patch("requests.post") as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()
        notifier.send_scrape_summary(summary, duration=10.0)

    text = mock_post.call_args[1]["json"]["text"]
    assert "錯誤" in text


def test_message_shows_success_when_no_failures():
    notifier = TelegramNotifier(token="t", chat_id="1")
    summary = RunSummary()
    summary.record_new("src1")

    with patch("requests.post") as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()
        notifier.send_scrape_summary(summary, duration=5.0)

    text = mock_post.call_args[1]["json"]["text"]
    assert "全部完成" in text
