from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.event_handlers.cache_warmup_handler import CacheWarmupHandler
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


def test_handle_publishes_warmup_signal():
    """020-redis-caching-layer follow-up: warm-up is now a Redis Pub/Sub signal to backend's
    own listener, not an HTTP self-call to backend's endpoints."""
    mock_cache = MagicMock()

    CacheWarmupHandler(mock_cache).handle(_make_event())

    mock_cache.publish_warmup_signal.assert_called_once_with(reason="scraper_pipeline")


def test_handle_relies_on_cache_gateway_never_raising():
    """The handler itself adds no try/except — it trusts CacheGateway's "never raises"
    contract for publish_warmup_signal(), the same posture CacheInvalidationHandler takes
    for bump_version(). A fake that violates the contract propagates, by design."""
    mock_cache = MagicMock()
    mock_cache.publish_warmup_signal.side_effect = Exception("redis unreachable")

    with pytest.raises(Exception, match="redis unreachable"):
        CacheWarmupHandler(mock_cache).handle(_make_event())
