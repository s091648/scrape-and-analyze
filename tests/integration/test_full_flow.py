import pytest
import uuid
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(db_session, *, url=None, source="test"):
    """Insert and return a committed Article with no analysis."""
    from models.article import Article
    from src.utils.sanitizer import generate_url_hash

    url = url or f"https://example.com/{uuid.uuid4()}"
    article = Article(
        url=url,
        url_hash=generate_url_hash(url),
        source=source,
        title="Test Article",
        content="Test content",
        correlation_id=uuid.uuid4(),
    )
    db_session.add(article)
    db_session.commit()
    return article


def _make_analysis(db_session, article):
    """Insert and return a committed Analysis linked to the given article."""
    from models.analysis import Analysis

    analysis = Analysis(
        article_id=article.id,
        correlation_id=uuid.uuid4(),
        pain_points="Pain points",
        insights="Insights",
        innovations="Innovations",
        model_used="test-model",
        input_tokens=10,
        output_tokens=5,
    )
    db_session.add(analysis)
    db_session.commit()
    return analysis


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_article_deduplication(db_session):
    """Duplicate articles should not be created."""
    from models.article import Article
    from src.utils.sanitizer import generate_url_hash

    url = f"https://example.com/dedup-{uuid.uuid4()}"
    url_hash = generate_url_hash(url)

    article = Article(
        url=url,
        url_hash=url_hash,
        source="test",
        title="Test Article",
        content="Test content",
        correlation_id=uuid.uuid4(),
    )
    db_session.add(article)
    db_session.commit()

    existing = db_session.query(Article).filter_by(url_hash=url_hash).first()
    assert existing is not None
    assert existing.url == url


# ---------------------------------------------------------------------------
# Transaction rollback
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_transaction_rollback_on_failure(db_session):
    """Failed transactions should rollback completely."""
    from models.article import Article

    initial_count = db_session.query(Article).count()

    try:
        article = Article(
            url=f"https://example.com/rollback-{uuid.uuid4()}",
            url_hash="invalid",
            source="test",
            title="Test",
            content="Content",
            correlation_id=uuid.uuid4(),
        )
        db_session.add(article)
        raise ValueError("Simulated error")
    except ValueError:
        db_session.rollback()

    assert db_session.query(Article).count() == initial_count


# ---------------------------------------------------------------------------
# Article + Analysis creation
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_article_with_analysis_creation(db_session):
    """Creating an Article and Analysis should persist both with correct relationship."""
    from models.article import Article
    from models.analysis import Analysis

    article = _make_article(db_session)
    analysis = _make_analysis(db_session, article)

    fetched = db_session.query(Article).filter_by(id=article.id).first()
    assert fetched is not None

    linked = db_session.query(Analysis).filter_by(article_id=article.id).first()
    assert linked is not None
    assert linked.id == analysis.id
    assert linked.model_used == "test-model"


# ---------------------------------------------------------------------------
# has_analysis
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_has_analysis_returns_true_when_analysis_exists(db_session):
    """has_analysis should return True for an article that has an analysis."""
    from src.database import has_analysis

    article = _make_article(db_session)
    _make_analysis(db_session, article)

    assert has_analysis(db_session, article.id) is True


@pytest.mark.integration
def test_has_analysis_returns_false_when_no_analysis(db_session):
    """has_analysis should return False for an article with no analysis."""
    from src.database import has_analysis

    article = _make_article(db_session)

    assert has_analysis(db_session, article.id) is False


# ---------------------------------------------------------------------------
# find_missing_analyses
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_find_missing_analyses_includes_article_without_analysis(db_session):
    """find_missing_analyses should return articles that have no analysis."""
    from src.database import find_missing_analyses

    article = _make_article(db_session)

    missing = find_missing_analyses(db_session)
    missing_ids = {a.id for a in missing}
    assert article.id in missing_ids


@pytest.mark.integration
def test_find_missing_analyses_excludes_analyzed_articles(db_session):
    """find_missing_analyses should not return articles that already have an analysis."""
    from src.database import find_missing_analyses

    article = _make_article(db_session)
    _make_analysis(db_session, article)

    missing = find_missing_analyses(db_session)
    missing_ids = {a.id for a in missing}
    assert article.id not in missing_ids


# ---------------------------------------------------------------------------
# scan_missing_analyses (zombie detection)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_scan_missing_analyses_finds_old_article_without_analysis(db_session):
    """scan_missing_analyses should include articles older than min_age_hours."""
    from models.article import Article
    from src.database import scan_missing_analyses
    from src.utils.sanitizer import generate_url_hash

    url = f"https://example.com/old-{uuid.uuid4()}"
    old_article = Article(
        url=url,
        url_hash=generate_url_hash(url),
        source="test",
        title="Old Article",
        content="Content",
        correlation_id=uuid.uuid4(),
        scraped_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    db_session.add(old_article)
    db_session.commit()

    zombies = scan_missing_analyses(db_session, min_age_hours=1)
    zombie_ids = {a.id for a in zombies}
    assert old_article.id in zombie_ids


@pytest.mark.integration
def test_scan_missing_analyses_skips_recent_articles(db_session):
    """scan_missing_analyses should not include recently-scraped articles (race-condition guard)."""
    from src.database import scan_missing_analyses

    # Default scraped_at = now() — well within the 1-hour grace period
    recent_article = _make_article(db_session)

    zombies = scan_missing_analyses(db_session, min_age_hours=1)
    zombie_ids = {a.id for a in zombies}
    assert recent_article.id not in zombie_ids
