from unittest.mock import MagicMock, patch
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats


def _make_event():
    return PipelineCompletedEvent(
        stats=[
            SourceStats(source="arxiv", new=3, duplicate=1, failed=0),
            SourceStats(source="rss", new=0, duplicate=0, failed=2),
        ],
        duration_seconds=8.0,
    )


def test_handler_fires_new_counter_per_source():
    from src.infrastructure.collection.handlers.otel_metrics_handler import OtelMetricsHandler

    mock_new = MagicMock()
    mock_dup = MagicMock()
    mock_err = MagicMock()

    with patch("src.infrastructure.collection.handlers.otel_metrics_handler.SCRAPER_ARTICLES_NEW", mock_new), \
         patch("src.infrastructure.collection.handlers.otel_metrics_handler.SCRAPER_ARTICLES_DUPLICATE", mock_dup), \
         patch("src.infrastructure.collection.handlers.otel_metrics_handler.SCRAPER_ERRORS", mock_err):

        OtelMetricsHandler().handle(_make_event())

    mock_new.add.assert_any_call(3, {"source": "arxiv"})
    mock_new.add.assert_any_call(0, {"source": "rss"})
    mock_dup.add.assert_any_call(1, {"source": "arxiv"})
    mock_err.add.assert_any_call(2, {"source": "rss"})