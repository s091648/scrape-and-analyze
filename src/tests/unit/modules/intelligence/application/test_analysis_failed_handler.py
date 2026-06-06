"""
Unit tests for AnalysisFailedHandler.
"""
import uuid
from unittest.mock import MagicMock, call

from src.modules.intelligence.application.events import AnalysisFailedEvent
from src.modules.collection.domain.entities import FailedTask


def _make_event(**kwargs):
    defaults = dict(
        article_id=uuid.uuid4(),
        article_url="https://example.com/article",
        exception_type="LLMAnalysisError",
        exception_message="All providers failed",
    )
    defaults.update(kwargs)
    return AnalysisFailedEvent(**defaults)


def test_handler_saves_failed_task_with_analyze_type():
    from src.modules.intelligence.application.event_handlers import AnalysisFailedHandler

    repo = MagicMock()
    handler = AnalysisFailedHandler(failed_task_repository=repo)
    event = _make_event()

    handler.handle(event)

    repo.save.assert_called_once()
    task: FailedTask = repo.save.call_args[0][0]
    assert isinstance(task, FailedTask)
    assert task.task_type == "analyze"
    assert task.article_id == event.article_id
    assert task.article_url == event.article_url
    assert task.exception_type == event.exception_type
    assert task.exception_message == event.exception_message
    assert task.failed_at is not None
    assert task.resolved is False


def test_handler_does_not_raise_when_repo_save_fails():
    from src.modules.intelligence.application.event_handlers import AnalysisFailedHandler

    repo = MagicMock()
    repo.save.side_effect = Exception("DB unavailable")
    handler = AnalysisFailedHandler(failed_task_repository=repo)

    # Should log and swallow the exception, not propagate
    handler.handle(_make_event())
