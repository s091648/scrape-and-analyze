"""
Integration tests for the article processing pipeline.

Uses ProcessArticleUseCase + real PostgreSQL (isolated test schema) and a
mocked LLM analyzer to exercise the full persist + analyze code paths.
"""
import pytest
import uuid
from unittest.mock import MagicMock

from src.analysis.providers.base_llm_provider import AnalysisResult
from src.ingestion.models.scraped_article import ScrapedArticle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**overrides):
    defaults = dict(
        tag_groups=[],
        pain_points="Test pain points",
        insights="Test insights",
        innovations="Test innovations",
        summary="Test summary.",
        input_tokens=100,
        output_tokens=50,
        model_used="test-model",
    )
    defaults.update(overrides)
    return AnalysisResult(**defaults)


def _make_scraped(**overrides):
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
    analyzer = MagicMock()
    analyzer.analyze.return_value = result if result is not None else (
        _make_result() if use_default else None
    )
    return analyzer


def _make_process_uc(db_session, analyzer):
    """Wire ProcessArticleUseCase against the shared test session."""
    from src.infrastructure.persistence.sqlalchemy_repos.article_repo_impl import (
        SqlAlchemyArticleRepository,
    )
    from src.infrastructure.persistence.sqlalchemy_repos.analysis_repo_impl import (
        SqlAlchemyAnalysisRepository,
    )
    from src.domain.services.dedup_service import DedupService
    from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
    from src.app.use_cases.process_article import ProcessArticleUseCase

    article_repo = SqlAlchemyArticleRepository(session=db_session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=db_session)
    dedup = DedupService(article_repo=article_repo)
    analyze_uc = AnalyzeArticleUseCase(analyzer=analyzer, analysis_repo=analysis_repo)
    return ProcessArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        analyze_article_uc=analyze_uc,
    )


# ---------------------------------------------------------------------------
# Happy path: new article
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_creates_article_and_analysis(db_session):
    """A new article should be persisted together with its LLM analysis."""
    from models.article import Article
    from models.analysis import Analysis

    scraped = _make_scraped()
    uc = _make_process_uc(db_session, _mock_analyzer())
    result = uc.execute(scraped, "test prompt", str(uuid.uuid4()))

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
    from models.article import Article

    scraped = _make_scraped()
    correlation_id = str(uuid.uuid4())

    # First call — creates article + analysis
    _make_process_uc(db_session, _mock_analyzer()).execute(scraped, "test prompt", correlation_id)

    analyzer = _mock_analyzer()
    result = _make_process_uc(db_session, analyzer).execute(scraped, "test prompt", correlation_id)

    assert result is False
    analyzer.analyze.assert_not_called()
    assert db_session.query(Article).filter_by(url=scraped.url).count() == 1


@pytest.mark.integration
def test_process_article_analyzes_duplicate_missing_analysis(db_session):
    """A duplicate URL that has NO analysis should still be analyzed."""
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

    result = _make_process_uc(db_session, _mock_analyzer()).execute(
        scraped, "test prompt", str(uuid.uuid4())
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
    from models.article import Article

    analyzer = _mock_analyzer(
        _make_result(tag_groups=[{"group": tag_group.name, "tags": ["AI", "IoT"]}])
    )
    scraped = _make_scraped()

    _make_process_uc(db_session, analyzer).execute(scraped, "test prompt", str(uuid.uuid4()))

    article = db_session.query(Article).filter_by(url=scraped.url).first()
    tag_names = {t.name for t in article.tags}
    assert "AI" in tag_names
    assert "IoT" in tag_names
    for tag in article.tags:
        assert tag.tag_group_name == tag_group.name


@pytest.mark.integration
def test_process_article_reuses_existing_tag(db_session, tag_group):
    """The same tag name+group on two different articles should produce only one Tag row."""
    from models.tag import Tag

    tag_payload = [{"group": tag_group.name, "tags": ["SharedTag"]}]

    _make_process_uc(db_session, _mock_analyzer(_make_result(tag_groups=tag_payload))).execute(
        _make_scraped(), "test prompt", str(uuid.uuid4())
    )
    _make_process_uc(db_session, _mock_analyzer(_make_result(tag_groups=tag_payload))).execute(
        _make_scraped(), "test prompt", str(uuid.uuid4())
    )

    count = db_session.query(Tag).filter_by(
        name="SharedTag", tag_group_name=tag_group.name
    ).count()
    assert count == 1


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_returns_false_when_analyzer_returns_none(db_session):
    """When the analyzer returns None, execute() returns False."""
    scraped = _make_scraped()
    analyzer = _mock_analyzer(result=None, use_default=False)

    result = _make_process_uc(db_session, analyzer).execute(
        scraped, "test prompt", str(uuid.uuid4())
    )

    assert result is False
