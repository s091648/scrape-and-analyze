from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


def _make_event():
    return PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=3, duplicate=1, failed=0)],
        execution=JobExecutionMeta(
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            duration_seconds=8.0,
            app_env="production",
        ),
    )


def test_handle_bumps_articles_namespace():
    from src.modules.collection.application.event_handlers.cache_invalidation_handler import CacheInvalidationHandler

    mock_cache = MagicMock()
    CacheInvalidationHandler(mock_cache).handle(_make_event())

    mock_cache.bump_version.assert_any_call("articles")


def test_handle_bumps_graph_namespace():
    from src.modules.collection.application.event_handlers.cache_invalidation_handler import CacheInvalidationHandler

    mock_cache = MagicMock()
    CacheInvalidationHandler(mock_cache).handle(_make_event())

    mock_cache.bump_version.assert_any_call("graph")


def test_handle_bumps_exactly_two_namespaces():
    from src.modules.collection.application.event_handlers.cache_invalidation_handler import CacheInvalidationHandler

    mock_cache = MagicMock()
    CacheInvalidationHandler(mock_cache).handle(_make_event())

    assert mock_cache.bump_version.call_count == 2
