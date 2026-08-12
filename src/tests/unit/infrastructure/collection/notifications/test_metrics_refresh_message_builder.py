"""Tests for MetricsRefreshMessageBuilder."""
from datetime import datetime, timezone

from src.modules.collection.application.events import MetricsRefreshCompletedEvent
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


def _make_execution(duration=5.0):
    return JobExecutionMeta(
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        duration_seconds=duration,
        app_env="production",
    )


def _make_event(total=10, refreshed=8, failed=2, duration=5.0, rate_limited_providers=()):
    return MetricsRefreshCompletedEvent(
        total=total, refreshed=refreshed, failed=failed, execution=_make_execution(duration=duration),
        rate_limited_providers=tuple(rate_limited_providers),
    )


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


def test_build_surfaces_rate_limited_providers():
    """A run where every article got skipped due to a rate-limited provider
    must be visible in the notification — not indistinguishable from
    "nothing needed updating" (both otherwise show refreshed=0, failed=0)."""
    from src.infrastructure.collection.notifications import MetricsRefreshMessageBuilder

    msg = MetricsRefreshMessageBuilder.build(_make_event(
        total=200, refreshed=0, failed=0, rate_limited_providers=("semantic_scholar_arxiv",),
    ))
    text = msg.text.replace("\\", "")
    assert "semantic_scholar_arxiv" in text
    assert "限流" in text


def test_build_omits_rate_limited_line_when_none():
    from src.infrastructure.collection.notifications import MetricsRefreshMessageBuilder

    msg = MetricsRefreshMessageBuilder.build(_make_event(rate_limited_providers=()))
    assert "限流" not in msg.text.replace("\\", "")
