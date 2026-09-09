import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from src.modules.intelligence.application.events.analysis_failed import AnalysisFailedEvent
from src.modules.intelligence.application.events.tag_normalization_failed import TagNormalizationFailedEvent
from src.modules.intelligence.application.events.translation_failed import TranslationFailedEvent
from src.modules.collection.domain.entities import FailedTask


def _make_repo():
    return AsyncMock()


@pytest.mark.asyncio
async def test_handles_analysis_failed_event():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    event = AnalysisFailedEvent(
        article_id=uuid.uuid4(), article_url="https://x.com", exception_type="LLMError",
        exception_message="failed",
    )
    await handler.handle(event)

    repo.save.assert_called_once()
    task: FailedTask = repo.save.call_args[0][0]
    assert task.task_type == "analyze"
    assert task.article_url == "https://x.com"
    assert task.exception_type == "LLMError"
    assert task.resolved is False


@pytest.mark.asyncio
async def test_handles_tag_normalization_failed_event():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    analysis_id = uuid.uuid4()
    event = TagNormalizationFailedEvent(
        analysis_id=analysis_id, article_id=uuid.uuid4(),
        exception_type="EmbeddingError", exception_message="quota exceeded",
        context={"group": "digital_twin"},
    )
    await handler.handle(event)

    repo.save.assert_called_once()
    task: FailedTask = repo.save.call_args[0][0]
    assert task.task_type == "tag_normalization"
    assert task.analysis_id == analysis_id
    assert task.context == {"group": "digital_twin"}


@pytest.mark.asyncio
async def test_handles_translation_failed_event():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    event = TranslationFailedEvent(
        analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
        task_type="translate_article", context={"language": "zh-TW"},
    )
    await handler.handle(event)

    task: FailedTask = repo.save.call_args[0][0]
    assert task.task_type == "translate_article"
    assert task.context == {"language": "zh-TW"}


@pytest.mark.asyncio
async def test_does_not_raise_when_repo_fails():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    repo.save.side_effect = Exception("DB down")
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    # Should not propagate the exception
    await handler.handle(AnalysisFailedEvent(article_id=uuid.uuid4(), article_url="https://x.com"))


@pytest.mark.asyncio
async def test_reconciles_pipeline_stats_partial_failure_when_provided():
    """When a pipeline_stats is injected, a downstream-stage failure for an
    already-saved article must be recorded as a partial failure (the article was
    counted as `new` at scrape time; the run summary needs to know a later stage
    failed)."""
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    stats = MagicMock()
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo, pipeline_stats=stats)
    article_id = uuid.uuid4()
    await handler.handle(AnalysisFailedEvent(article_id=article_id, article_url="https://x.com"))

    stats.record_partial_failure.assert_called_once_with(article_id)
    repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_stats_bookkeeping_failure_never_blocks_persistence():
    """A raise from pipeline_stats.record_partial_failure must be swallowed — the
    FailedTask still has to be persisted."""
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    stats = MagicMock()
    stats.record_partial_failure.side_effect = RuntimeError("stats blew up")
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo, pipeline_stats=stats)
    await handler.handle(AnalysisFailedEvent(article_id=uuid.uuid4(), article_url="https://x.com"))

    repo.save.assert_called_once()
