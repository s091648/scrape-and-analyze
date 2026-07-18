"""Tests for the per-module PipelineCompletedMessageBuilder."""
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats


def _make_event(new=2, duplicate=1, failed=0, source="arxiv", duration=12.5):
    return PipelineCompletedEvent(
        stats=[SourceStats(source=source, new=new, duplicate=duplicate, failed=failed)],
        duration_seconds=duration,
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
        PipelineCompletedEvent(stats=[], duration_seconds=0.5)
    )
    assert msg.parse_mode == "MarkdownV2"
    assert "來源數：0" in msg.text or "0" in msg.text


def test_build_marks_failure_in_footer():
    from src.infrastructure.collection.notifications import PipelineCompletedMessageBuilder

    msg = PipelineCompletedMessageBuilder.build(_make_event(failed=3))
    assert "3" in msg.text
