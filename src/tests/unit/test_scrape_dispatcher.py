from unittest.mock import MagicMock


def test_pipeline_publishes_events_for_each_scraped_article():
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.modules.collection.domain.entities import ScraperSetting
    from src.modules.collection.domain.value_objects import ScrapedArticle
    from uuid import uuid4

    # Mock setting repo
    setting = ScraperSetting(
        source="test-rss", source_type="rss",
        url="https://example.com/feed", interval_hours=24,
    )
    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [setting]

    # Mock scraper factory + scraper - fetch returns ScrapedArticle (domain object)
    article1 = ScrapedArticle(url="https://example.com/1", title="T1",
                              content="C", source="test-rss")
    article2 = ScrapedArticle(url="https://example.com/2", title="T2",
                              content="C", source="test-rss")

    from src.modules.collection.domain.entities import ScrapeJob
    job1 = ScrapeJob(url="https://example.com/1", source="test-rss", source_type="rss")
    job2 = ScrapeJob(url="https://example.com/2", source="test-rss", source_type="rss")

    scraper = MagicMock()
    scraper.discover.return_value = [job1, job2]
    scraper.fetch.side_effect = [article1, article2]

    scraper_factory = MagicMock()
    scraper_factory.create_for.return_value = scraper

    event_bus = MagicMock()
    pipeline_stats = MagicMock()

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
    )
    pipeline.run()

    # Should publish ScrapedArticleDTO for each article (plus PipelineCompletedEvent at end)
    from src.modules.collection.application.dtos import ScrapedArticleDTO
    article_publishes = [
        c for c in event_bus.publish.call_args_list
        if isinstance(c.args[0], ScrapedArticleDTO)
    ]
    assert len(article_publishes) == 2


def test_pipeline_marks_setting_scraped_after_run():
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.modules.collection.domain.entities import ScraperSetting
    from uuid import uuid4

    setting = ScraperSetting(
        source="test", source_type="rss",
        url="https://example.com/feed", interval_hours=24,
    )
    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [setting]

    scraper = MagicMock()
    scraper.discover.return_value = []
    scraper_factory = MagicMock()
    scraper_factory.create_for.return_value = scraper

    event_bus = MagicMock()
    pipeline_stats = MagicMock()

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
    )
    pipeline.run()

    setting_repo.mark_scraped.assert_called_once_with(setting.id)