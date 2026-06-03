"""
Unit tests for OTel span attributes in CollectionPipeline stage spans.

Verifies that each stage span carries the expected attributes so operators
can identify bottlenecks from trace data.
"""
from unittest.mock import MagicMock, patch, call
import pytest


def _make_pipeline_with_articles(article_count: int = 3):
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.collection.executor.fetch_task import FetchTask

    mock_setting = MagicMock()
    mock_setting.source_type = "rss"
    mock_setting.url = "https://example.com/feed.xml"
    mock_setting.id = "setting-1"

    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [mock_setting]

    fake_fetch_tasks = [
        FetchTask(
            url=f"https://example.com/article-{i}",
            source="example",
            job=MagicMock(url=f"https://example.com/article-{i}", source="example"),
            scraper=MagicMock(),
        )
        for i in range(article_count)
    ]

    def fake_run_discover(discover_tasks, pre_fetch_filter=None):
        return fake_fetch_tasks

    def fake_run_fetch_only(fetch_tasks, on_result):
        from src.modules.collection.domain.value_objects import ScrapedArticle
        for i in range(article_count):
            article = ScrapedArticle(
                url=f"https://example.com/article-{i}",
                title=f"Article {i}",
                content="Test content",
                source="example",
            )
            on_result(article)

    executor = MagicMock()
    executor.run_discover = fake_run_discover
    executor.run_fetch_only = fake_run_fetch_only

    event_bus = MagicMock()
    pipeline_stats = MagicMock()
    pipeline_stats.get_results.return_value = []

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=MagicMock(),
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        executor=executor,
    )
    return pipeline


class TestPipelineSpanAttributes:
    def _capture_spans(self, pipeline):
        """Run pipeline with mock tracer and capture span names + attributes."""
        calls = {}

        class TrackingSpan:
            def __init__(self, name):
                self.name = name
                self._attrs = {}
                calls[name] = self

            def set_attribute(self, k, v):
                self._attrs[k] = v

            def record_exception(self, e): pass
            def set_status(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False

        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.side_effect = lambda name: TrackingSpan(name)

        with patch("src.infrastructure.shared.observability.otel_tracing._tracer", mock_tracer):
            pipeline.run()

        return calls

    def test_discover_span_has_sources_count(self):
        pipeline = _make_pipeline_with_articles(3)
        spans = self._capture_spans(pipeline)
        assert "pipeline.discover" in spans
        span = spans["pipeline.discover"]
        assert span._attrs.get("sources.count") == 1
        assert "articles.discovered" in span._attrs

    def test_fetch_span_has_article_counts(self):
        pipeline = _make_pipeline_with_articles(3)
        spans = self._capture_spans(pipeline)
        assert "pipeline.fetch" in spans
        span = spans["pipeline.fetch"]
        assert "articles.to_fetch" in span._attrs
        assert "articles.fetched" in span._attrs

    def test_dedup_span_has_article_counts(self):
        pipeline = _make_pipeline_with_articles(3)
        spans = self._capture_spans(pipeline)
        assert "pipeline.dedup" in spans
        span = spans["pipeline.dedup"]
        assert "articles.before_dedup" in span._attrs
        assert "articles.after_dedup" in span._attrs
        assert "articles.skipped" in span._attrs

    def test_publish_span_has_published_count(self):
        pipeline = _make_pipeline_with_articles(3)
        spans = self._capture_spans(pipeline)
        assert "pipeline.publish_articles" in spans
        span = spans["pipeline.publish_articles"]
        assert "articles.published" in span._attrs
