import uuid
from unittest.mock import MagicMock, patch

from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    TagNormalizationCompletedEvent,
    TagNormalizationFailedEvent,
)
from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsResult


def _make_handler():
    from src.modules.intelligence.application.event_handlers.tag_normalization_handler import (
        TagNormalizationHandler,
    )
    uc = MagicMock()
    bus = MagicMock()
    session = MagicMock()
    return TagNormalizationHandler(use_case=uc, event_bus=bus, session=session), uc, bus


def _make_event(tag_groups=(("digital_twin", ["virtual replica"]),)):
    return AnalysisCompletedEvent(
        analysis_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        tag_groups=tag_groups,
    )


def test_publishes_completed_event_on_success():
    handler, uc, bus = _make_handler()
    uc.execute.return_value = NormalizeTagsResult(
        success=True, analysis_id=uuid.uuid4(), article_id=uuid.uuid4()
    )
    event = _make_event()
    handler.handle(event)

    bus.publish.assert_called_once()
    published = bus.publish.call_args[0][0]
    assert isinstance(published, TagNormalizationCompletedEvent)
    assert published.analysis_id == event.analysis_id


def test_publishes_failed_event_on_failure():
    handler, uc, bus = _make_handler()
    uc.execute.return_value = NormalizeTagsResult(
        success=False, analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
        exception_type="EmbeddingError", exception_message="quota exceeded",
    )
    event = _make_event()
    handler.handle(event)

    published = bus.publish.call_args[0][0]
    assert isinstance(published, TagNormalizationFailedEvent)
    assert published.exception_type == "EmbeddingError"


# ── Span attribute tests ──────────────────────────────────────────────────────

def test_span_records_analysis_and_article_ids():
    handler, uc, _bus = _make_handler()
    event = _make_event()
    uc.execute.return_value = NormalizeTagsResult(
        success=True, analysis_id=event.analysis_id, article_id=event.article_id
    )
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(event)

    mock_span.set_attribute.assert_any_call("analysis.id", str(event.analysis_id))
    mock_span.set_attribute.assert_any_call("article.id", str(event.article_id))


def test_span_records_tag_counts():
    handler, uc, _bus = _make_handler()
    event = _make_event(tag_groups=(
        ("technology", ["AI", "ML"]),
        ("industry", ["finance"]),
    ))
    uc.execute.return_value = NormalizeTagsResult(
        success=True, analysis_id=event.analysis_id, article_id=event.article_id
    )
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(event)

    mock_span.set_attribute.assert_any_call("tags.group_count", 2)
    mock_span.set_attribute.assert_any_call("tags.total_count", 3)


def test_span_records_normalization_success():
    handler, uc, _bus = _make_handler()
    event = _make_event()
    uc.execute.return_value = NormalizeTagsResult(
        success=True, analysis_id=event.analysis_id, article_id=event.article_id
    )
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(event)

    mock_span.set_attribute.assert_any_call("normalization.success", True)


def test_span_records_error_type_on_failure():
    handler, uc, _bus = _make_handler()
    event = _make_event()
    uc.execute.return_value = NormalizeTagsResult(
        success=False, analysis_id=event.analysis_id, article_id=event.article_id,
        exception_type="EmbeddingError", exception_message="quota",
    )
    mock_span = MagicMock()

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        handler.handle(event)

    mock_span.set_attribute.assert_any_call("normalization.success", False)
    mock_span.set_attribute.assert_any_call("normalization.error_type", "EmbeddingError")
