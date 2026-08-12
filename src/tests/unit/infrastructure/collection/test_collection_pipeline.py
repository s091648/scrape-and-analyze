from unittest.mock import MagicMock, call, patch

from src.infrastructure.collection.collection_pipeline import CollectionPipeline
from src.modules.collection.application.use_cases import PipelineStats
from src.infrastructure.collection.executor.fetch_task import FetchTask


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
    mock_executor.run_discover.return_value = []

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
    def capture_discover(discover_tasks, pre_fetch_filter=None):
        nonlocal captured_filter
        captured_filter = pre_fetch_filter
        return []
    mock_executor.run_discover.side_effect = capture_discover

    pipeline = _make_pipeline(
        setting_repo=mock_setting_repo,
        article_repo=mock_article_repo,
        executor=mock_executor,
    )
    pipeline.run()

    assert captured_filter is not None
    from src.modules.collection.domain.value_objects import UrlHash
    mock_task = MagicMock()
    mock_task.url = "https://example.com/article1"
    analyzed_hash = UrlHash.from_url(mock_task.url).value
    mock_article_repo.find_analyzed_url_hashes.return_value = {analyzed_hash}
    filtered = captured_filter([mock_task])
    mock_article_repo.find_analyzed_url_hashes.assert_called()
    assert filtered == []


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
    mock_executor.run_discover.return_value = [MagicMock(), MagicMock(), MagicMock()]
    def fetch_with_dupes(fetch_tasks, on_result):
        on_result(article1)
        on_result(article2)
        on_result(article3)
    mock_executor.run_fetch_only.side_effect = fetch_with_dupes

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


def test_intra_batch_dedup_logs_article_duplicate_skipped():
    """Duplicates caught within the same fetch batch must emit the same
    'article_duplicate_skipped' event the frontend's Duplicate Articles chart
    queries — previously only ArticleScrapedHandler logged it, which never fires
    for URLs deduped upstream in the pipeline (the common case)."""
    from src.modules.collection.domain.value_objects import ScrapedArticle

    mock_setting_repo = MagicMock()
    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    mock_setting_repo.get_active_due.return_value = [setting]

    mock_article_repo = MagicMock()
    mock_article_repo.find_analyzed_url_hashes.return_value = set()

    article1 = ScrapedArticle(title="A1", url="https://example.com/dup", source="rss", content="c1", published_at=None)
    article2 = ScrapedArticle(title="A2", url="https://example.com/dup", source="rss", content="c2", published_at=None)

    mock_executor = MagicMock()
    mock_executor.run_discover.return_value = [MagicMock(), MagicMock()]
    def fetch_with_dupes(fetch_tasks, on_result):
        on_result(article1)
        on_result(article2)
    mock_executor.run_fetch_only.side_effect = fetch_with_dupes

    pipeline = _make_pipeline(
        setting_repo=mock_setting_repo,
        article_repo=mock_article_repo,
        executor=mock_executor,
    )

    with patch("src.infrastructure.collection.collection_pipeline.logger") as mock_logger:
        pipeline.run()

    mock_logger.info.assert_any_call(
        "article_duplicate_skipped", url="https://example.com/dup", source="rss", original_source=None,
    )


def test_run_publishes_rate_limited_hosts_and_llm_providers():
    """PipelineCompletedEvent must report ScrapeExecutor.exhausted_hosts and
    llm_service.exhausted_providers when the pipeline was given an llm_service —
    otherwise a rate-limited run looks identical to a clean one."""
    from src.modules.collection.application.events import PipelineCompletedEvent

    mock_setting_repo = MagicMock()
    mock_setting_repo.get_active_due.return_value = []

    mock_executor = MagicMock()
    mock_executor.exhausted_hosts = ["export.arxiv.org"]

    mock_llm_service = MagicMock()
    mock_llm_service.exhausted_providers = ["gemini"]

    mock_event_bus = MagicMock()
    pipeline = CollectionPipeline(
        setting_repo=mock_setting_repo,
        scraper_factory=MagicMock(),
        event_bus=mock_event_bus,
        pipeline_stats=PipelineStats(),
        executor=mock_executor,
        llm_service=mock_llm_service,
    )
    pipeline.run()

    published = mock_event_bus.publish.call_args.args[0]
    assert isinstance(published, PipelineCompletedEvent)
    assert published.rate_limited_hosts == ("export.arxiv.org",)
    assert published.rate_limited_llm_providers == ("gemini",)


def test_run_reports_no_rate_limited_llm_providers_when_not_wired():
    """CollectionPipeline built without an llm_service (e.g. an older caller)
    must not blow up reading .exhausted_providers — just report none."""
    from src.modules.collection.application.events import PipelineCompletedEvent

    mock_setting_repo = MagicMock()
    mock_setting_repo.get_active_due.return_value = []
    mock_executor = MagicMock()
    mock_executor.exhausted_hosts = []
    mock_event_bus = MagicMock()

    pipeline = _make_pipeline(setting_repo=mock_setting_repo, event_bus=mock_event_bus, executor=mock_executor)
    pipeline.run()

    published = mock_event_bus.publish.call_args.args[0]
    assert isinstance(published, PipelineCompletedEvent)
    assert published.rate_limited_llm_providers == ()


def test_post_fetch_dedup_logs_article_duplicate_skipped():
    """Duplicates caught by the post-fetch already-analyzed check must also emit
    'article_duplicate_skipped', matching what ArticleScrapedHandler logs for the
    (rarer) duplicate detected inside ProcessScrapedArticleUseCase."""
    from src.modules.collection.domain.value_objects import ScrapedArticle, UrlHash

    mock_setting_repo = MagicMock()
    setting = MagicMock(id="id-1", source_type="rss", url="https://example.com/feed")
    mock_setting_repo.get_active_due.return_value = [setting]

    article = ScrapedArticle(title="A1", url="https://example.com/already-analyzed", source="rss", content="c1", published_at=None)
    analyzed_hash = UrlHash.from_url(article.url).value

    mock_article_repo = MagicMock()
    mock_article_repo.find_analyzed_url_hashes.return_value = {analyzed_hash}

    mock_executor = MagicMock()
    mock_executor.run_discover.return_value = [MagicMock()]
    def fetch_one(fetch_tasks, on_result):
        on_result(article)
    mock_executor.run_fetch_only.side_effect = fetch_one

    pipeline = _make_pipeline(
        setting_repo=mock_setting_repo,
        article_repo=mock_article_repo,
        executor=mock_executor,
    )

    with patch("src.infrastructure.collection.collection_pipeline.logger") as mock_logger:
        result = pipeline.run()

    assert result == 0
    mock_logger.info.assert_any_call(
        "article_duplicate_skipped", url=article.url, source="rss", original_source=None,
    )
