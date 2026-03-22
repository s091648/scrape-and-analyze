"""
Integration tests for the core article processing pipeline (src/main.py).

These tests use a real PostgreSQL database (isolated test schema) and a
mocked LLM analyzer to exercise the full process_article / analyze_article
code paths without hitting external APIs.
"""
import pytest
import uuid
from unittest.mock import MagicMock

from src.analyzers.providers import AnalysisResult
from src.scrapers.scrapers.article import ScrapedArticle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**overrides):
    """Build a minimal AnalysisResult, merging any overrides."""
    defaults = dict(
        tag_groups=[],
        pain_points="Test pain points",
        insights="Test insights",
        innovations="Test innovations",
        input_tokens=100,
        output_tokens=50,
        model_used="test-model",
    )
    defaults.update(overrides)
    return AnalysisResult(**defaults)


def _make_scraped(**overrides):
    """Build a ScrapedArticle with a unique URL by default."""
    defaults = dict(
        url=f"https://example.com/article/{uuid.uuid4()}",
        title="Test Article",
        content="Content about digital twins.",
        published_at=None,
        source="test",
    )
    defaults.update(overrides)
    return ScrapedArticle(**defaults)


def _mock_analyzer(result=None, *, use_default=True):
    """Return a MagicMock analyzer whose .analyze() returns result."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = result if result is not None else (
        _make_result() if use_default else None
    )
    return analyzer


# ---------------------------------------------------------------------------
# Happy path: new article
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_creates_article_and_analysis(db_session):
    """A new article should be persisted together with its LLM analysis."""
    from src.main import process_article
    from models.article import Article
    from models.analysis import Analysis

    scraped = _make_scraped()
    result = process_article(
        db_session, scraped, _mock_analyzer(), "test prompt", str(uuid.uuid4())
    )

    assert result is True

    article = db_session.query(Article).filter_by(url=scraped.url).first()
    assert article is not None
    assert article.title == scraped.title
    assert article.source == scraped.source

    analysis = db_session.query(Analysis).filter_by(article_id=article.id).first()
    assert analysis is not None
    assert analysis.pain_points == "Test pain points"
    assert analysis.model_used == "test-model"
    assert analysis.input_tokens == 100


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_returns_false_for_fully_processed_duplicate(db_session):
    """A duplicate URL that already has an analysis should return False without re-analyzing."""
    from src.main import process_article
    from models.article import Article

    scraped = _make_scraped()
    correlation_id = str(uuid.uuid4())

    # First call — creates article + analysis
    process_article(db_session, scraped, _mock_analyzer(), "test prompt", correlation_id)

    analyzer = _mock_analyzer()
    result = process_article(db_session, scraped, analyzer, "test prompt", correlation_id)

    assert result is False
    # Analyzer should NOT have been called a second time
    analyzer.analyze.assert_not_called()

    # Still only one Article row
    assert db_session.query(Article).filter_by(url=scraped.url).count() == 1


@pytest.mark.integration
def test_process_article_analyzes_duplicate_missing_analysis(db_session):
    """A duplicate URL that has NO analysis should still be analyzed."""
    from src.main import process_article
    from models.article import Article
    from models.analysis import Analysis
    from src.utils.sanitizer import generate_url_hash

    scraped = _make_scraped()

    # Pre-insert article without analysis
    article = Article(
        url=scraped.url,
        url_hash=generate_url_hash(scraped.url),
        source=scraped.source,
        title=scraped.title,
        content=scraped.content,
        correlation_id=uuid.uuid4(),
    )
    db_session.add(article)
    db_session.commit()

    result = process_article(
        db_session, scraped, _mock_analyzer(), "test prompt", str(uuid.uuid4())
    )

    assert result is True
    analysis = db_session.query(Analysis).filter_by(article_id=article.id).first()
    assert analysis is not None


# ---------------------------------------------------------------------------
# Tag creation and reuse
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_creates_tags_and_links_to_article(db_session, tag_group):
    """analyze_article should create Tag rows and associate them with the article."""
    from src.main import process_article
    from models.article import Article
    from models.tag import Tag

    analyzer = _mock_analyzer(
        _make_result(tag_groups=[{"group": tag_group.name, "tags": ["AI", "IoT"]}])
    )
    scraped = _make_scraped()

    process_article(db_session, scraped, analyzer, "test prompt", str(uuid.uuid4()))

    article = db_session.query(Article).filter_by(url=scraped.url).first()
    tag_names = {t.name for t in article.tags}
    assert "AI" in tag_names
    assert "IoT" in tag_names

    # Tags should be in the correct group
    for tag in article.tags:
        assert tag.tag_group_name == tag_group.name


@pytest.mark.integration
def test_process_article_reuses_existing_tag(db_session, tag_group):
    """The same tag name+group on two different articles should produce only one Tag row."""
    from src.main import process_article
    from models.tag import Tag

    tag_payload = [{"group": tag_group.name, "tags": ["SharedTag"]}]

    # Process two independent articles, both tagged "SharedTag"
    process_article(
        db_session, _make_scraped(), _mock_analyzer(_make_result(tag_groups=tag_payload)),
        "test prompt", str(uuid.uuid4())
    )
    process_article(
        db_session, _make_scraped(), _mock_analyzer(_make_result(tag_groups=tag_payload)),
        "test prompt", str(uuid.uuid4())
    )

    count = db_session.query(Tag).filter_by(
        name="SharedTag", tag_group_name=tag_group.name
    ).count()
    assert count == 1


# ---------------------------------------------------------------------------
# Failure recording
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_records_failure_when_analyzer_returns_none(db_session):
    """When the analyzer returns None a FailedTask should be created for task_type='analyze'."""
    from src.main import process_article
    from models.failed_task import FailedTask

    scraped = _make_scraped()
    analyzer = _mock_analyzer(result=None, use_default=False)

    result = process_article(db_session, scraped, analyzer, "test prompt", str(uuid.uuid4()))

    assert result is False

    failure = db_session.query(FailedTask).filter_by(
        article_url=scraped.url, task_type="analyze"
    ).first()
    assert failure is not None
    assert failure.exception_type == "Exception"
    assert failure.resolved is False
