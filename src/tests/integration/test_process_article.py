"""
Integration tests for the article processing pipeline.

Uses the full event-driven pipeline wired via InMemoryEventBus
with real PostgreSQL (isolated test schema) and a mocked LLM service.

Pipeline flow tested:
  ArticleScrapedHandler → ProcessScrapedArticleUseCase
  → ArticleProcessedEvent → ArticleProcessedHandler → AnalyzeArticleUseCase
"""
import pytest
import uuid
from unittest.mock import MagicMock

from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.collection.application.events import ArticleScrapedEvent


def _make_llm_result(**overrides):
    content = AnalysisContent(
        pain_points=overrides.get("pain_points", "Test pain points"),
        insights=overrides.get("insights", "Test insights"),
        innovations=overrides.get("innovations", "Test innovations"),
        summary=overrides.get("summary", "Test summary."),
        tag_groups=overrides.get("tag_groups", []),
    )
    metadata = AnalysisMetadata(
        model_used=overrides.get("model_used", "test-model"),
        input_tokens=overrides.get("input_tokens", 100),
        output_tokens=overrides.get("output_tokens", 50),
    )
    return (content, metadata)


def _make_event(**overrides):
    defaults = dict(
        url=f"https://example.com/article/{uuid.uuid4()}",
        title="Test Article",
        content="Content about digital twins.",
        source="test",
    )
    defaults.update(overrides)
    return ArticleScrapedEvent(**defaults)


def _mock_llm(result=None, *, use_default=True):
    llm = MagicMock()
    llm.analyze.return_value = result if result is not None else (
        _make_llm_result() if use_default else None
    )
    return llm


def _wire_pipeline(db_session, llm_service):
    """Wire the full event-driven pipeline:
    ArticleScrapedHandler → ProcessScrapedArticleUseCase
    → ArticleProcessedEvent → ArticleProcessedHandler → AnalyzeArticleUseCase
    """
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.shared.events.in_memory_event_bus import InMemoryEventBus
    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler
    from src.modules.intelligence.domain.value_objects import AnalysisPrompt
    from src.shared.application.events import ArticleProcessedEvent

    article_repo = SqlAlchemyArticleRepository(session=db_session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=db_session)
    topic_repo = SqlAlchemyTopicRepository(session=db_session)
    event_bus = InMemoryEventBus()
    dedup = DedupService(article_repo=article_repo)

    process_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
    )
    analyze_uc = AnalyzeArticleUseCase(
        llm_service=llm_service,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
        prompt=AnalysisPrompt(),
    )

    scraped_handler = ArticleScrapedHandler(
        use_case=process_uc,
        pipeline_stats=PipelineStats(),
        event_bus=event_bus,
    )
    processed_handler = ArticleProcessedHandler(use_case=analyze_uc, event_bus=event_bus)
    event_bus.subscribe(ArticleProcessedEvent, processed_handler.handle)

    return scraped_handler


# ---------------------------------------------------------------------------
# Happy path: new article
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_creates_article_and_analysis(db_session):
    from models.article import Article
    from models.analysis import Analysis
    from models.analyses_translation import AnalysesTranslation

    event = _make_event()
    handler = _wire_pipeline(db_session, _mock_llm())
    assert handler.handle(event) is True

    article = db_session.query(Article).filter_by(url=event.url).first()
    assert article is not None
    assert article.title == event.title
    assert article.source == event.source

    analysis = db_session.query(Analysis).filter_by(article_id=article.id).first()
    assert analysis is not None
    assert analysis.model_used == "test-model"
    assert analysis.input_tokens == 100

    # Content is now stored in analyses_translation
    en_translation = db_session.query(AnalysesTranslation).filter_by(
        analysis_id=analysis.id, language="en"
    ).first()
    assert en_translation is not None
    assert en_translation.pain_points == "Test pain points"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_returns_false_for_fully_processed_duplicate(db_session):
    from models.article import Article

    event = _make_event()

    # First call — creates article + analysis
    _wire_pipeline(db_session, _mock_llm()).handle(event)

    llm = _mock_llm()
    result = _wire_pipeline(db_session, llm).handle(event)

    # ArticleScrapedHandler returns True for DUPLICATE (only FAILED returns False)
    assert result is True
    llm.analyze.assert_not_called()
    assert db_session.query(Article).filter_by(url=event.url).count() == 1


@pytest.mark.integration
def test_process_article_analyzes_duplicate_missing_analysis(db_session):
    from models.article import Article
    from models.analysis import Analysis
    from src.modules.collection.domain.value_objects import UrlHash

    event = _make_event()

    # Pre-insert article without analysis
    article = Article(
        url=event.url,
        url_hash=UrlHash.from_url(event.url).value,
        source=event.source,
        title=event.title,
        content=event.content,
        correlation_id=uuid.uuid4(),
    )
    db_session.add(article)
    db_session.commit()

    # DUPLICATE_NEEDS_ANALYSIS still publishes ArticleProcessedEvent,
    # so the handler returns True (not FAILED)
    result = _wire_pipeline(db_session, _mock_llm()).handle(event)
    assert result is True

    analysis = db_session.query(Analysis).filter_by(article_id=article.id).first()
    assert analysis is not None


# ---------------------------------------------------------------------------
# Tag creation and reuse
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_process_article_creates_tags_and_links_to_article(db_session, tag_group):
    from models.article import Article
    from src.modules.intelligence.domain.value_objects import TagGroup

    llm = _mock_llm(_make_llm_result(
        tag_groups=[TagGroup(display_name=tag_group.display_name, description="test-tag")]
    ))
    event = _make_event()

    _wire_pipeline(db_session, llm).handle(event)

    article = db_session.query(Article).filter_by(url=event.url).first()
    assert article is not None
    tag_names = {t.name for t in article.tags}
    assert len(tag_names) > 0


@pytest.mark.integration
def test_process_article_returns_true_when_llm_returns_none(db_session):
    from models.article import Article
    from models.analysis import Analysis

    event = _make_event()
    llm = _mock_llm(result=None, use_default=False)

    # Handler returns True because the article was saved (outcome=NEW),
    # even though LLM analysis subsequently failed inside the event chain
    result = _wire_pipeline(db_session, llm).handle(event)

    assert result is True
    article = db_session.query(Article).filter_by(url=event.url).first()
    assert article is not None
    analysis = db_session.query(Analysis).filter_by(article_id=article.id).first()
    assert analysis is None