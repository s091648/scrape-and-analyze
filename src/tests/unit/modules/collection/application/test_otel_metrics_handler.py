from unittest.mock import MagicMock, patch
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.use_cases import SourceStats


def _make_event(stats=None, duration=8.0):
    return PipelineCompletedEvent(
        stats=stats or [
            SourceStats(source="arxiv", new=3, duplicate=1, failed=0),
            SourceStats(source="rss", new=0, duplicate=0, failed=2),
        ],
        duration_seconds=duration,
    )


def test_handler_sets_duration_attribute():
    from src.infrastructure.collection.handlers.otel_metrics_handler import OtelMetricsHandler

    mock_span = MagicMock()
    with patch("src.infrastructure.collection.handlers.otel_metrics_handler._otel_trace") as mock_trace:
        mock_trace.get_current_span.return_value = mock_span
        OtelMetricsHandler().handle(_make_event(duration=12.5))

    mock_span.set_attribute.assert_any_call("pipeline.duration_seconds", 12.5)


def test_handler_sets_sources_count_attribute():
    from src.infrastructure.collection.handlers.otel_metrics_handler import OtelMetricsHandler

    mock_span = MagicMock()
    with patch("src.infrastructure.collection.handlers.otel_metrics_handler._otel_trace") as mock_trace:
        mock_trace.get_current_span.return_value = mock_span
        OtelMetricsHandler().handle(_make_event())

    mock_span.set_attribute.assert_any_call("pipeline.sources_count", 2)


def test_handler_sources_count_matches_stats_length():
    from src.infrastructure.collection.handlers.otel_metrics_handler import OtelMetricsHandler

    stats = [
        SourceStats(source="arxiv", new=5, duplicate=2, failed=1),
        SourceStats(source="rss", new=3, duplicate=4, failed=0),
        SourceStats(source="blog", new=1, duplicate=0, failed=3),
    ]
    mock_span = MagicMock()
    with patch("src.infrastructure.collection.handlers.otel_metrics_handler._otel_trace") as mock_trace:
        mock_trace.get_current_span.return_value = mock_span
        OtelMetricsHandler().handle(_make_event(stats=stats, duration=10.0))

    mock_span.set_attribute.assert_any_call("pipeline.sources_count", 3)
    mock_span.set_attribute.assert_any_call("pipeline.duration_seconds", 10.0)
