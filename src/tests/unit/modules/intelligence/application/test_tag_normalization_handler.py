import uuid
from unittest.mock import MagicMock

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
    return TagNormalizationHandler(use_case=uc, event_bus=bus), uc, bus


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
