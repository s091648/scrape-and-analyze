def test_scrape_job_accepts_topic_id():
    from uuid import uuid4
    from src.modules.collection.domain.entities import ScrapeJob
    tid = uuid4()
    job = ScrapeJob(url="https://example.com", source="rss",
                    source_type="rss", topic_id=tid)
    assert job.topic_id == tid


def test_scrape_job_topic_id_defaults_to_none():
    from src.modules.collection.domain.entities import ScrapeJob
    job = ScrapeJob(url="https://x.com", source="rss", source_type="rss")
    assert job.topic_id is None


def test_article_entity_accepts_topic_id():
    from uuid import uuid4
    from src.shared.domain.entities import Article
    tid = uuid4()
    a = Article(
        url="https://x.com", url_hash="a" * 64,
        source="rss", title="T", content="C", topic_id=tid,
    )
    assert a.topic_id == tid


def test_article_scraped_event_accepts_topic_id():
    from uuid import uuid4
    from src.modules.collection.application.events import ArticleScrapedEvent
    tid = uuid4()
    ev = ArticleScrapedEvent(
        url="https://x.com", title="T", content="C",
        source="rss", topic_id=tid,
    )
    assert ev.topic_id == tid