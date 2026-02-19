import pytest


def test_article_model_has_required_fields():
    """Article model should have all required fields"""
    from src.models.article import Article

    assert hasattr(Article, 'id')
    assert hasattr(Article, 'url')
    assert hasattr(Article, 'url_hash')
    assert hasattr(Article, 'source')
    assert hasattr(Article, 'title')
    assert hasattr(Article, 'content')
    assert hasattr(Article, 'published_at')
    assert hasattr(Article, 'scraped_at')
    assert hasattr(Article, 'metadata_')
    assert hasattr(Article, 'correlation_id')


def test_article_url_is_unique():
    """Article url should have unique constraint"""
    from src.models.article import Article

    url_column = Article.__table__.columns['url']
    assert url_column.unique is True


def test_article_url_hash_has_index():
    """Article url_hash should have an index"""
    from src.models.article import Article

    indexes = {idx.name for idx in Article.__table__.indexes}
    assert any('url_hash' in idx for idx in indexes)
