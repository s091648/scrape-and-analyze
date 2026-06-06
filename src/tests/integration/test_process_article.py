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


def _wire_pipeline(db_session, llm_service, embedding_service=None):
    """Wire the full event-driven pipeline:
    ArticleScrapedHandler → ProcessScrapedArticleUseCase
    → ArticleProcessedEvent → ArticleProcessedHandler → AnalyzeArticleUseCase
    → AnalysisCompletedEvent → TagNormalizationHandler → NormalizeTagsUseCase (if embedding_service provided)
    """
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.persistence.intelligence.tag_group_definition_repo_impl import SqlAlchemyTagGroupDefinitionRepository
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
    tag_group_def_repo = SqlAlchemyTagGroupDefinitionRepository(session=db_session)
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
        tag_group_definition_repository=tag_group_def_repo,
        prompt=AnalysisPrompt(),
    )

    scraped_handler = ArticleScrapedHandler(
        use_case=process_uc,
        pipeline_stats=PipelineStats(),
        event_bus=event_bus,
    )
    processed_handler = ArticleProcessedHandler(use_case=analyze_uc, event_bus=event_bus)
    event_bus.subscribe(ArticleProcessedEvent, processed_handler.handle)

    if embedding_service is not None:
        from src.infrastructure.persistence.intelligence.tag_repo_impl import SqlAlchemyTagRepository
        from src.modules.intelligence.application.use_cases import NormalizeTagsUseCase
        from src.modules.intelligence.application.event_handlers.tag_normalization_handler import TagNormalizationHandler
        from src.modules.intelligence.application.events import AnalysisCompletedEvent

        tag_repo = SqlAlchemyTagRepository(session=db_session)
        normalize_uc = NormalizeTagsUseCase(
            embedding_service=embedding_service,
            tag_repository=tag_repo,
        )
        tag_norm_handler = TagNormalizationHandler(use_case=normalize_uc, event_bus=event_bus)
        event_bus.subscribe(AnalysisCompletedEvent, tag_norm_handler.handle)

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
    from src.modules.intelligence.domain.value_objects import AnalysisTagGroup

    embedding_svc = MagicMock()
    embedding_svc.embed_batch.return_value = [[0.1] * 768]

    llm = _mock_llm(_make_llm_result(
        tag_groups=[AnalysisTagGroup(group_name=tag_group.name, tags=["test-tag"])]
    ))
    event = _make_event(topic_id=tag_group.topic_id)

    _wire_pipeline(db_session, llm, embedding_svc).handle(event)

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


# ---------------------------------------------------------------------------
# ArXiv metadata persistence (US1-AC2, FR-005)
# ---------------------------------------------------------------------------

def _wire_pipeline_with_arxiv_repo(db_session, llm_service):
    """Wire pipeline with a real SqlAlchemyArxivMetadataRepository."""
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.collection.arxiv_metadata_repo_impl import SqlAlchemyArxivMetadataRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.persistence.intelligence.tag_group_definition_repo_impl import SqlAlchemyTagGroupDefinitionRepository
    from src.infrastructure.shared.events.in_memory_event_bus import InMemoryEventBus
    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler
    from src.modules.intelligence.domain.value_objects import AnalysisPrompt
    from src.shared.application.events import ArticleProcessedEvent

    article_repo = SqlAlchemyArticleRepository(session=db_session)
    arxiv_repo = SqlAlchemyArxivMetadataRepository(session=db_session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=db_session)
    topic_repo = SqlAlchemyTopicRepository(session=db_session)
    tag_group_def_repo = SqlAlchemyTagGroupDefinitionRepository(session=db_session)
    event_bus = InMemoryEventBus()
    dedup = DedupService(article_repo=article_repo)

    process_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        arxiv_metadata_repo=arxiv_repo,
    )
    analyze_uc = AnalyzeArticleUseCase(
        llm_service=llm_service,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
        tag_group_definition_repository=tag_group_def_repo,
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


@pytest.mark.integration
def test_process_arxiv_article_persists_metadata(db_session):
    from models.arxiv_metadata import ArxivMetadata as ArxivMetadataModel
    from models.article import Article as ArticleModel

    event = ArticleScrapedEvent(
        url=f"https://arxiv.org/abs/{uuid.uuid4()}",
        title="ArXiv Test Paper",
        content="Abstract text here.",
        source="arxiv",
        metadata={
            "arxiv_id": "2501.00001",
            "authors": ["Author A", "Author B"],
            "pdf_available": True,
            "sections": {"introduction": "Intro text."},
        },
    )
    handler = _wire_pipeline_with_arxiv_repo(db_session, _mock_llm())
    assert handler.handle(event) is True

    article = db_session.query(ArticleModel).filter_by(url=event.url).first()
    assert article is not None

    meta = db_session.query(ArxivMetadataModel).filter_by(article_id=article.id).first()
    assert meta is not None
    assert meta.arxiv_id == "2501.00001"
    assert "Author A" in meta.authors
    assert meta.pdf_available is True


# ---------------------------------------------------------------------------
# ArXiv section merging on re-queue (US3-AC2, FR-007)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_requeue_arxiv_article_merges_sections_from_stored_metadata(db_session):
    from models.article import Article as ArticleModel
    from models.arxiv_metadata import ArxivMetadata as ArxivMetadataModel
    from src.modules.collection.domain.value_objects import UrlHash
    from src.shared.application.events import ArticleProcessedEvent

    url = f"https://arxiv.org/abs/{uuid.uuid4()}"
    url_hash = UrlHash.from_url(url).value

    # Pre-insert article without analysis
    article_row = ArticleModel(
        url=url,
        url_hash=url_hash,
        source="arxiv",
        title="Re-queue Test Paper",
        content="Abstract only.",
        correlation_id=uuid.uuid4(),
    )
    db_session.add(article_row)
    db_session.flush()

    # Pre-insert ArxivMetadata with sections
    meta_row = ArxivMetadataModel(
        article_id=article_row.id,
        arxiv_id="2501.99999",
        authors=["Test Author"],
        pdf_available=True,
        sections={"introduction": "This is the full intro."},
    )
    db_session.add(meta_row)
    db_session.commit()

    # Capture the ArticleProcessedEvent to inspect the re-queued article
    captured = []

    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.collection.arxiv_metadata_repo_impl import SqlAlchemyArxivMetadataRepository
    from src.infrastructure.shared.events.in_memory_event_bus import InMemoryEventBus
    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler

    article_repo = SqlAlchemyArticleRepository(session=db_session)
    arxiv_repo = SqlAlchemyArxivMetadataRepository(session=db_session)
    event_bus = InMemoryEventBus()
    dedup = DedupService(article_repo=article_repo)
    process_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        arxiv_metadata_repo=arxiv_repo,
    )
    handler = ArticleScrapedHandler(
        use_case=process_uc,
        pipeline_stats=PipelineStats(),
        event_bus=event_bus,
    )
    event_bus.subscribe(ArticleProcessedEvent, lambda e: captured.append(e.article))

    event = ArticleScrapedEvent(
        url=url,
        title="Re-queue Test Paper",
        content="Abstract only.",
        source="arxiv",
    )
    result = handler.handle(event)

    assert result is True
    assert len(captured) == 1
    assert captured[0].metadata.get("sections") == {"introduction": "This is the full intro."}