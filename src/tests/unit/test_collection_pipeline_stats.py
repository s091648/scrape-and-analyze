from unittest.mock import MagicMock, patch
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats
from src.modules.collection.application.events.pipeline_completed import PipelineCompletedEvent
from src.modules.collection.domain.value_objects import ScrapedArticle


def _make_setting(source="arxiv"):
    s = MagicMock()
    s.source = source
    s.id = "test-id"
    return s


def _make_scraper(articles):
    scraper = MagicMock()
    scraper.discover.return_value = [MagicMock(url=f"http://x.com/{i}") for i in range(len(articles))]
    scraper.fetch.side_effect = articles
    return scraper


def test_pipeline_publishes_pipeline_completed_event():
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline

    pipeline_stats = PipelineStats()
    event_bus = MagicMock()

    # simulate handler recording outcomes by having event_bus.publish side_effect
    def _fake_publish(event):
        if isinstance(event, PipelineCompletedEvent):
            return True
        # When ScrapedArticleDTO is published, simulate handler recording NEW
        pipeline_stats.record(event.source, ArticleOutcome.NEW)
        return True

    event_bus.publish.side_effect = _fake_publish

    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [_make_setting("arxiv")]

    scraper_factory = MagicMock()
    scraper = MagicMock()
    scraper.discover.return_value = [MagicMock(url="http://x.com/1")]
    article = MagicMock(spec=ScrapedArticle)
    article.url = "http://x.com/1"
    article.source = "arxiv"
    article.title = "T"
    article.content = "C"
    article.published_at = None
    article.topic_id = None
    article.authors = []
    article.extra = {}
    scraper.fetch.return_value = article
    scraper_factory.create_for.return_value = scraper

    executor = MagicMock()
    executor.run.side_effect = lambda tasks, on_result: on_result(article)

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        executor=executor,
    )
    pipeline.run()

    # verify PipelineCompletedEvent was published
    published_events = [
        call.args[0] for call in event_bus.publish.call_args_list
        if isinstance(call.args[0], PipelineCompletedEvent)
    ]
    assert len(published_events) == 1
    assert published_events[0].duration_seconds >= 0