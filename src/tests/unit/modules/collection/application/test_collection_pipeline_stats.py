from unittest.mock import MagicMock
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats
from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.domain.value_objects import ScrapedArticle


def _make_setting(source="arxiv", source_type="arxiv"):
    s = MagicMock()
    s.source = source
    s.source_type = source_type
    s.url = "https://export.arxiv.org/api/query"
    s.id = "test-id"
    return s


def test_pipeline_publishes_pipeline_completed_event():
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline

    pipeline_stats = PipelineStats()
    event_bus = MagicMock()

    article = MagicMock(spec=ScrapedArticle)
    article.url = "http://x.com/1"
    article.source = "arxiv"
    article.title = "T"
    article.content = "C"
    article.published_at = None
    article.topic_id = None
    article.authors = []
    article.extra = {}

    def _fake_publish(event):
        if isinstance(event, PipelineCompletedEvent):
            return True
        pipeline_stats.record(event.source, ArticleOutcome.NEW)
        return True

    event_bus.publish.side_effect = _fake_publish

    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [_make_setting("arxiv")]

    scraper_factory = MagicMock()

    executor = MagicMock()
    mock_fetch_task = MagicMock()
    executor.run_discover.return_value = [mock_fetch_task]
    def _run_fetch_only(fetch_tasks, on_result):
        on_result(article)
    executor.run_fetch_only.side_effect = _run_fetch_only

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        executor=executor,
    )
    pipeline.run()

    published_events = [
        call.args[0] for call in event_bus.publish.call_args_list
        if isinstance(call.args[0], PipelineCompletedEvent)
    ]
    assert len(published_events) == 1
    assert published_events[0].duration_seconds >= 0
