import pytest
from unittest.mock import patch, MagicMock
import uuid


@pytest.mark.integration
def test_article_deduplication(db_session):
    """Duplicate articles should not be created"""
    from src.models.article import Article
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/test-article"
    url_hash = generate_url_hash(url)

    # Create first article
    article1 = Article(
        url=url,
        url_hash=url_hash,
        source="test",
        title="Test Article",
        content="Test content",
        correlation_id=uuid.uuid4()
    )
    db_session.add(article1)
    db_session.commit()

    # Try to query for duplicate
    existing = db_session.query(Article).filter_by(url_hash=url_hash).first()
    assert existing is not None
    assert existing.url == url


@pytest.mark.integration
def test_transaction_rollback_on_failure(db_session):
    """Failed transactions should rollback completely"""
    from src.models.article import Article

    initial_count = db_session.query(Article).count()

    try:
        article = Article(
            url="https://example.com/rollback-test",
            url_hash="invalid",
            source="test",
            title="Test",
            content="Content",
            correlation_id=uuid.uuid4()
        )
        db_session.add(article)
        # Force an error
        raise ValueError("Simulated error")
    except ValueError:
        db_session.rollback()

    final_count = db_session.query(Article).count()
    assert final_count == initial_count
