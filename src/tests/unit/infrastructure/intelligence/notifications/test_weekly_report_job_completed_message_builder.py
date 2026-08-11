"""Tests for WeeklyReportJobCompletedMessageBuilder."""
from datetime import datetime, timezone

from src.modules.intelligence.application.events import WeeklyReportJobCompletedEvent
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


def _make_execution(duration=5.0):
    return JobExecutionMeta(
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        duration_seconds=duration,
        app_env="production",
    )


def _make_event(total_topics=5, generated=4, failed=1, duration=5.0):
    return WeeklyReportJobCompletedEvent(
        total_topics=total_topics, generated=generated, failed=failed, execution=_make_execution(duration=duration),
    )


def test_build_returns_telegram_message_with_markdownv2():
    from src.infrastructure.intelligence.notifications import WeeklyReportJobCompletedMessageBuilder

    msg = WeeklyReportJobCompletedMessageBuilder.build(_make_event())
    assert msg.parse_mode == "MarkdownV2"


def test_build_includes_counts():
    from src.infrastructure.intelligence.notifications import WeeklyReportJobCompletedMessageBuilder

    msg = WeeklyReportJobCompletedMessageBuilder.build(_make_event(total_topics=5, generated=4, failed=1))
    assert "5" in msg.text
    assert "4" in msg.text
    assert "1" in msg.text


def test_build_marks_failure_in_footer():
    from src.infrastructure.intelligence.notifications import WeeklyReportJobCompletedMessageBuilder

    msg = WeeklyReportJobCompletedMessageBuilder.build(_make_event(failed=3))
    assert "有 3 個 topic 生成失敗" in msg.text.replace("\\", "")
    assert "全部完成" not in msg.text


def test_build_handles_zero_failures():
    from src.infrastructure.intelligence.notifications import WeeklyReportJobCompletedMessageBuilder

    msg = WeeklyReportJobCompletedMessageBuilder.build(_make_event(total_topics=5, generated=5, failed=0))
    assert msg.parse_mode == "MarkdownV2"
    assert "全部完成" in msg.text
    assert "個 topic 生成失敗，請檢查" not in msg.text.replace("\\", "")
