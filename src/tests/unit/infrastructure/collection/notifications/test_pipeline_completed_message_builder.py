"""Tests for the per-module PipelineCompletedMessageBuilder."""
from datetime import datetime, timezone

from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


def _make_execution(duration=12.5, app_env="production", jitter_seconds=None):
    return JobExecutionMeta(
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        duration_seconds=duration,
        app_env=app_env,
        jitter_seconds=jitter_seconds,
    )


def _make_event(new=2, duplicate=1, failed=0, source="arxiv", duration=12.5):
    return PipelineCompletedEvent(
        stats=[SourceStats(source=source, new=new, duplicate=duplicate, failed=failed)],
        execution=_make_execution(duration=duration),
    )


def test_build_returns_telegram_message_with_markdownv2():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event())
    assert msg.parse_mode == "MarkdownV2"
    assert "arxiv" in msg.text


def test_build_includes_source_name():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event(source="my_rss_feed"))
    assert "my_rss_feed" in msg.text


def test_build_handles_empty_stats():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(
        PipelineCompletedEvent(stats=[], execution=_make_execution(duration=0.5))
    )
    assert msg.parse_mode == "MarkdownV2"
    assert "來源數：0" in msg.text or "0" in msg.text


def test_build_marks_failure_in_footer():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event(failed=3))
    assert "3" in msg.text


def test_build_shows_environment_badge_when_not_production():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    event = PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=1, duplicate=0, failed=0)],
        execution=_make_execution(app_env="staging"),
    )
    msg = PipelineCompletedMessageBuilder.build(event)
    assert "staging" in msg.text.replace("\\", "")


def test_build_omits_environment_badge_when_production():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event())
    assert "環境" not in msg.text


def test_build_includes_jitter_when_present():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    event = PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=1, duplicate=0, failed=0)],
        execution=_make_execution(jitter_seconds=42.0),
    )
    msg = PipelineCompletedMessageBuilder.build(event)
    assert "jitter" in msg.text.replace("\\", "")


def test_build_surfaces_rate_limited_hosts_and_llm_providers():
    """A run where a scrape source and/or LLM provider got rate-limited must be
    visible — the two ID spaces (hostname vs LLM provider_name) are reported
    as separate lines rather than merged into one list."""
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    event = PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=1, duplicate=0, failed=0)],
        execution=_make_execution(),
        rate_limited_hosts=("export.arxiv.org",),
        rate_limited_llm_providers=("gemini",),
    )
    msg = PipelineCompletedMessageBuilder.build(event)
    text = msg.text.replace("\\", "")
    assert "export.arxiv.org" in text
    assert "gemini" in text
    assert "限流" in text


def test_build_omits_rate_limited_lines_when_none():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event())
    assert "限流" not in msg.text.replace("\\", "")


def test_build_reports_partial_failures_when_scrape_stage_clean():
    """Articles saved but with a later stage (analysis/translate/RAG) failing are
    a distinct count from SourceStats.failed — surfaced in both the body and the
    footer even when no scrape/save failed."""
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    event = PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=5, duplicate=0, failed=0)],
        execution=_make_execution(),
        partial_failure_count=2,
    )
    text = PipelineCompletedMessageBuilder.build(event).text.replace("\\", "")
    assert "部分失敗" in text
    assert "2" in text


def test_build_combines_hard_and_partial_failures_in_footer():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    event = PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=4, duplicate=0, failed=3)],
        execution=_make_execution(),
        partial_failure_count=1,
    )
    text = PipelineCompletedMessageBuilder.build(event).text.replace("\\", "")
    assert "3" in text and "另有 1 篇部分失敗" in text


def test_build_omits_partial_failure_line_when_zero():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event())
    assert "部分失敗" not in msg.text.replace("\\", "")


def test_build_surfaces_rag_daily_quota_skips():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    event = PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=10, duplicate=0, failed=0)],
        execution=_make_execution(),
        rag_rate_limited_skipped=7,
    )
    text = PipelineCompletedMessageBuilder.build(event).text.replace("\\", "")
    assert "RAG" in text and "7" in text and "backfill" in text


def test_build_omits_rag_quota_line_when_zero():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event())
    assert "RPD" not in msg.text and "backfill" not in msg.text
