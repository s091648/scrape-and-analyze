from unittest.mock import MagicMock, patch

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.modules.collection.application.use_cases import PipelineStats


def _make_pipeline(setting_repo=None, event_bus=None, article_repo=None, executor=None):
    return CollectionPipeline(
        setting_repo=setting_repo or MagicMock(),
        scraper_factory=MagicMock(),
        event_bus=event_bus or MagicMock(),
        pipeline_stats=PipelineStats(),
        article_repo=article_repo,
        executor=executor or MagicMock(),
    )


def test_mark_scraped_called_for_each_due_setting():
    """T042: Verify mark_scraped() is called for each due setting after discovery."""
    mock_setting_repo = MagicMock()
    setting1 = MagicMock(id="id-1", source_type="rss", url="https://a.com/feed")
    setting2 = MagicMock(id="id-2", source_type="rss", url="https://b.com/feed")
    mock_setting_repo.get_active_due.return_value = [setting1, setting2]

    mock_executor = MagicMock()
    mock_executor.run_streaming.return_value = 0

    pipeline = _make_pipeline(setting_repo=mock_setting_repo, executor=mock_executor)
    pipeline.run()

    assert mock_setting_repo.mark_scraped.call_count == 2
    call_ids = {c[0][0] for c in mock_setting_repo.mark_scraped.call_args_list}
    assert "id-1" in call_ids
    assert "id-2" in call_ids


def test_pre_fetch_dedup_filters_analyzed_urls():
    """T043: Verify pre-fetch dedup filter checks URL hashes against already-analyzed articles."""
    mock_setting_repo = MagicMock()
    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    mock_setting_repo.get_active_due.return_value = [setting]

    mock_article_repo = MagicMock()
    # Simulate that all URLs are already analyzed
    mock_article_repo.find_analyzed_url_hashes.return_value = {"hash1", "hash2"}

    mock_executor = MagicMock()
    # Capture the pre_fetch_filter callback
    captured_filter = None
    def capture_streaming(discover_tasks, on_result, pre_fetch_filter=None):
        nonlocal captured_filter
        captured_filter = pre_fetch_filter
    mock_executor.run_streaming.side_effect = capture_streaming

    pipeline = _make_pipeline(
        setting_repo=mock_setting_repo,
        article_repo=mock_article_repo,
        executor=mock_executor,
    )
    pipeline.run()

    assert captured_filter is not None
    # Verify the filter calls find_analyzed_url_hashes
    mock_task = MagicMock()
    mock_task.url = "https://example.com/article1"
    captured_filter([mock_task])
    mock_article_repo.find_analyzed_url_hashes.assert_called()


def test_post_fetch_dedup_removes_duplicate_urls():
    """T044: Verify post-fetch dedup removes duplicate URLs from results."""
    from src.modules.collection.domain.value_objects import ScrapedArticle, UrlHash

    mock_setting_repo = MagicMock()
    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    mock_setting_repo.get_active_due.return_value = [setting]

    mock_article_repo = MagicMock()
    # No analyzed URLs (skip post-fetch analyzed check)
    mock_article_repo.find_analyzed_url_hashes.return_value = set()

    # Create articles with duplicate URLs
    article1 = ScrapedArticle(title="A1", url="https://example.com/dup", source="test", content="c1", published_at=None)
    article2 = ScrapedArticle(title="A2", url="https://example.com/dup", source="test", content="c2", published_at=None)
    article3 = ScrapedArticle(title="A3", url="https://example.com/unique", source="test", content="c3", published_at=None)

    mock_executor = MagicMock()
    def streaming_with_dupes(discover_tasks, on_result, pre_fetch_filter=None):
        on_result(article1)
        on_result(article2)
        on_result(article3)
    mock_executor.run_streaming.side_effect = streaming_with_dupes

    mock_event_bus = MagicMock()
    pipeline = _make_pipeline(
        setting_repo=mock_setting_repo,
        event_bus=mock_event_bus,
        article_repo=mock_article_repo,
        executor=mock_executor,
    )
    from src.modules.collection.application.events import ArticleScrapedEvent
    result = pipeline.run()

    # 3 articles fetched, but 2 had the same URL, so only 2 unique articles published
    assert result == 2
    article_publishes = sum(
        1 for c in mock_event_bus.publish.call_args_list
        if isinstance(c.args[0], ArticleScrapedEvent)
    )
    assert article_publishes == 2
