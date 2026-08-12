"""Tests for RagBackfillMessageBuilder."""
from datetime import datetime, timezone

from src.modules.intelligence.application.events import RagBackfillCompletedEvent
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


def _make_execution(duration=5.0):
    return JobExecutionMeta(
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        duration_seconds=duration,
        app_env="production",
    )


def _make_event(total=10, succeeded=8, failed=2, duration=5.0):
    return RagBackfillCompletedEvent(
        total=total, succeeded=succeeded, failed=failed, execution=_make_execution(duration=duration),
    )


def test_build_returns_telegram_message_with_markdownv2():
    from src.infrastructure.intelligence.notifications import RagBackfillMessageBuilder

    msg = RagBackfillMessageBuilder.build(_make_event())
    assert msg.parse_mode == "MarkdownV2"


def test_build_includes_counts():
    from src.infrastructure.intelligence.notifications import RagBackfillMessageBuilder

    msg = RagBackfillMessageBuilder.build(_make_event(total=10, succeeded=8, failed=2))
    assert "10" in msg.text
    assert "8" in msg.text
    assert "2" in msg.text


def test_build_marks_failure_in_footer():
    from src.infrastructure.intelligence.notifications import RagBackfillMessageBuilder

    msg = RagBackfillMessageBuilder.build(_make_event(failed=3))
    assert "有 3 篇補做向量化失敗" in msg.text.replace("\\", "")
    assert "全部完成" not in msg.text


def test_build_handles_zero_failures():
    from src.infrastructure.intelligence.notifications import RagBackfillMessageBuilder

    msg = RagBackfillMessageBuilder.build(_make_event(total=5, succeeded=5, failed=0))
    assert msg.parse_mode == "MarkdownV2"
    assert "全部完成" in msg.text
    assert "篇補做向量化失敗，請檢查" not in msg.text.replace("\\", "")
