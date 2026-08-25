from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_pipeline_publishes_events_for_each_scraped_article():
    """024-async-pipeline-refactor: ArticleScrapedEvent is now published on a
    fresh per-article bus (built by article_downstream_builder inside each
    article's own asyncio.Task), not the run-level event_bus — so this test
    tracks publishes via a spy subscribed inside a tracking
    article_downstream_builder instead of inspecting event_bus directly."""
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    from src.modules.collection.domain.entities import ScraperSetting
    from src.modules.collection.domain.value_objects import ScrapedArticle
    from src.modules.collection.application.events import ArticleScrapedEvent

    setting = ScraperSetting(
        source="test-rss", source_type="rss",
        url="https://example.com/feed", interval_hours=24,
    )
    setting_repo = MagicMock()
    setting_repo.get_active_due.return_value = [setting]

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

    event_bus = AsyncMock()
    pipeline_stats = MagicMock()

    seen_article_scraped_events = []

    @asynccontextmanager
    async def _fake_session():
        yield MagicMock()

    async def article_downstream_builder(session, bus, dispatch_rag):
        async def _spy(event):
            seen_article_scraped_events.append(event)
        await bus.subscribe(ArticleScrapedEvent, _spy)

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        async_sessionmaker_factory=lambda: _fake_session(),
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
    )
    await pipeline.run()

    assert len(seen_article_scraped_events) == 2


@pytest.mark.asyncio
async def test_pipeline_marks_setting_scraped_after_run():
    from src.infrastructure.collection.collection_pipeline import CollectionPipeline
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    from src.modules.collection.domain.entities import ScraperSetting

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

    event_bus = AsyncMock()
    pipeline_stats = MagicMock()

    async def article_downstream_builder(session, bus, dispatch_rag):
        pass

    pipeline = CollectionPipeline(
        setting_repo=setting_repo,
        scraper_factory=scraper_factory,
        event_bus=event_bus,
        pipeline_stats=pipeline_stats,
        async_sessionmaker_factory=lambda: None,
        article_downstream_builder=article_downstream_builder,
        rag_downstream_builder=None,
        event_bus_factory=AsyncInMemoryEventBus,
    )
    await pipeline.run()

    setting_repo.mark_scraped.assert_called_once_with(setting.id)
