def test_scraped_article_accepts_topic_id():
    from src.ingestion.models.scraped_article import ScrapedArticle
    a = ScrapedArticle(
        url="https://example.com", title="T", content="C",
        published_at=None, source="rss", topic_id="abc-123",
    )
    assert a.topic_id == "abc-123"


def test_scraped_article_topic_id_defaults_to_none():
    from src.ingestion.models.scraped_article import ScrapedArticle
    a = ScrapedArticle(url="https://x.com", title="T", content="C",
                       published_at=None, source="rss")
    assert a.topic_id is None


def test_article_entity_accepts_topic_id():
    from uuid import uuid4
    from src.domain.entities.article import ArticleEntity
    tid = uuid4()
    a = ArticleEntity(
        url="https://x.com", url_hash="abc", source="rss",
        title="T", content="C", correlation_id=uuid4(), topic_id=tid,
    )
    assert a.topic_id == tid
