"""Tests for MetricsRefreshMessageBuilder."""
from src.modules.collection.application.events import MetricsRefreshCompletedEvent


def _make_event(total=10, refreshed=8, failed=2, duration=5.0):
    return MetricsRefreshCompletedEvent(total=total, refreshed=refreshed, failed=failed, duration_seconds=duration)


def test_build_returns_telegram_message_with_markdownv2():
    from src.infrastructure.collection.notifications import MetricsRefreshMessageBuilder

    msg = MetricsRefreshMessageBuilder.build(_make_event())
    assert msg.parse_mode == "MarkdownV2"


def test_build_includes_counts():
    from src.infrastructure.collection.notifications import MetricsRefreshMessageBuilder

    msg = MetricsRefreshMessageBuilder.build(_make_event(total=10, refreshed=8, failed=2))
    assert "10" in msg.text
    assert "8" in msg.text
    assert "2" in msg.text


def test_build_marks_failure_in_footer():
    from src.infrastructure.collection.notifications import MetricsRefreshMessageBuilder

    msg = MetricsRefreshMessageBuilder.build(_make_event(failed=3))
    assert "有 3 篇更新失敗" in msg.text.replace("\\", "")
    assert "全部完成" not in msg.text


def test_build_handles_zero_failures():
    from src.infrastructure.collection.notifications import MetricsRefreshMessageBuilder

    msg = MetricsRefreshMessageBuilder.build(_make_event(total=5, refreshed=5, failed=0))
    assert msg.parse_mode == "MarkdownV2"
    assert "全部完成" in msg.text
    assert "篇更新失敗，請檢查" not in msg.text.replace("\\", "")
