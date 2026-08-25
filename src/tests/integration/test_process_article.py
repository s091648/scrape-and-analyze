"""
Integration tests for the article processing pipeline.

Uses the full event-driven pipeline wired via AsyncInMemoryEventBus
with real PostgreSQL (isolated test schema, async session) and a mocked
LLM service.

Pipeline flow tested:
  ArticleScrapedHandler → ProcessScrapedArticleUseCase
  → ArticleProcessedEvent → ArticleProcessedHandler → AnalyzeArticleUseCase

024-async-pipeline-refactor: ArticleScrapedHandler/ProcessScrapedArticleUseCase/
ArticleProcessedHandler/AnalyzeArticleUseCase/NormalizeTagsUseCase/
TagNormalizationHandler were converted to async in place — this file now wires
their async repository siblings and awaits `.handle()`.
"""
import pytest
import uuid
from unittest.mock import AsyncMock

from sqlalchemy import select

from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.collection.application.events import ArticleScrapedEvent

pytestmark = pytest.mark.integration


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
    llm = AsyncMock()
    llm.analyze.return_value = result if result is not None else (
        _make_llm_result() if use_default else None
    )
    return llm


async def _wire_pipeline_and_handle(async_session, llm_service, event, embedding_service=None):
    """Builds the pipeline (subscribing async handlers, which requires
    awaiting bus.subscribe()) and runs one event through it — a thin async
    wrapper since AsyncInMemoryEventBus.subscribe() is itself async."""
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_async_repo_impl import AsyncSqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_async_repo_impl import AsyncSqlAlchemyTopicRepository
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import AsyncSqlAlchemyTagGroupDefinitionRepository
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    from src.modules.collection.domain.services import AsyncDedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase, PipelineStats
    from src.modules.collection.application.event_handlers import ArticleScrapedHandler
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler
    from src.modules.intelligence.domain.value_objects import AnalysisPrompt
    from src.shared.application.events import ArticleProcessedEvent
    from src.modules.collection.application.events import ArticleScrapedEvent as _ArticleScrapedEvent

    article_repo = AsyncSqlAlchemyArticleRepository(session=async_session)
    analysis_repo = AsyncSqlAlchemyAnalysisRepository(session=async_session)
    topic_repo = AsyncSqlAlchemyTopicRepository(session=async_session)
    tag_group_def_repo = AsyncSqlAlchemyTagGroupDefinitionRepository(session=async_session)
    event_bus = AsyncInMemoryEventBus()
    dedup = AsyncDedupService(article_repo=article_repo)

    process_uc = ProcessScrapedArticleUseCase(article_repo=article_repo, dedup_service=dedup)
    analyze_uc = AnalyzeArticleUseCase(
        llm_service=llm_service,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
        tag_group_definition_repository=tag_group_def_repo,
        prompt=AnalysisPrompt(),
    )

    scraped_handler = ArticleScrapedHandler(use_case=process_uc, pipeline_stats=PipelineStats(), event_bus=event_bus)
    processed_handler = ArticleProcessedHandler(use_case=analyze_uc, event_bus=event_bus)
    await event_bus.subscribe(ArticleProcessedEvent, processed_handler.handle)

    if embedding_service is not None:
        from src.infrastructure.persistence.intelligence.tag_async_repo_impl import AsyncSqlAlchemyTagRepository
        from src.modules.intelligence.application.use_cases import NormalizeTagsUseCase
        from src.modules.intelligence.application.event_handlers.tag_normalization_handler import TagNormalizationHandler
        from src.modules.intelligence.application.events import AnalysisCompletedEvent

        tag_repo = AsyncSqlAlchemyTagRepository(session=async_session)
        normalize_uc = NormalizeTagsUseCase(embedding_service=embedding_service, tag_repository=tag_repo)
        tag_norm_handler = TagNormalizationHandler(use_case=normalize_uc, event_bus=event_bus, session=async_session)
        await event_bus.subscribe(AnalysisCompletedEvent, tag_norm_handler.handle)

    return await scraped_handler.handle(event)


# ---------------------------------------------------------------------------
# Happy path: new article
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_article_creates_article_and_analysis(async_db_session):
    from models.article import Article
    from models.analysis import Analysis
    from models.analyses_translation import AnalysesTranslation

    event = _make_event()
    result = await _wire_pipeline_and_handle(async_db_session, _mock_llm(), event)
    assert result is True

    article = (await async_db_session.execute(select(Article).filter_by(url=event.url))).scalars().first()
    assert article is not None
    assert article.title == event.title
    assert article.source == event.source

    analysis = (await async_db_session.execute(select(Analysis).filter_by(article_id=article.id))).scalars().first()
    assert analysis is not None
    assert analysis.model_used == "test-model"
    assert analysis.input_tokens == 100

    en_translation = (await async_db_session.execute(
        select(AnalysesTranslation).filter_by(analysis_id=analysis.id, language="en")
    )).scalars().first()
    assert en_translation is not None
    assert en_translation.pain_points == "Test pain points"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_article_returns_false_for_fully_processed_duplicate(async_db_session):
    from models.article import Article

    event = _make_event()

    # First call — creates article + analysis
    await _wire_pipeline_and_handle(async_db_session, _mock_llm(), event)
    await async_db_session.commit()

    llm = _mock_llm()
    result = await _wire_pipeline_and_handle(async_db_session, llm, event)

    # ArticleScrapedHandler returns True for DUPLICATE (only FAILED returns False)
    assert result is True
    llm.analyze.assert_not_called()
    count = (await async_db_session.execute(select(Article).filter_by(url=event.url))).scalars().all()
    assert len(count) == 1


@pytest.mark.asyncio
async def test_process_article_analyzes_duplicate_missing_analysis(async_db_session):
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
    async_db_session.add(article)
    await async_db_session.commit()

    # DUPLICATE_NEEDS_ANALYSIS still publishes ArticleProcessedEvent,
    # so the handler returns True (not FAILED)
    result = await _wire_pipeline_and_handle(async_db_session, _mock_llm(), event)
    assert result is True

    analysis = (await async_db_session.execute(select(Analysis).filter_by(article_id=article.id))).scalars().first()
    assert analysis is not None


# ---------------------------------------------------------------------------
# Tag creation and reuse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_article_creates_tags_and_links_to_article(async_db_session, tag_group):
    from models.article import Article
    from src.modules.intelligence.domain.value_objects import AnalysisTagGroup

    embedding_svc = AsyncMock()
    embedding_svc.embed_batch.return_value = [[0.1] * 768]

    llm = _mock_llm(_make_llm_result(
        tag_groups=[AnalysisTagGroup(group_name=tag_group.name, tags=["test-tag"])]
    ))
    event = _make_event(topic_id=tag_group.topic_id)

    await _wire_pipeline_and_handle(async_db_session, llm, event, embedding_service=embedding_svc)
    await async_db_session.commit()

    article = (await async_db_session.execute(
        select(Article).filter_by(url=event.url)
    )).scalars().first()
    assert article is not None

    from models.tag import Tag, article_tags
    tag_rows = (await async_db_session.execute(
        select(Tag).join(article_tags, article_tags.c.tag_id == Tag.id).filter(article_tags.c.article_id == article.id)
    )).scalars().all()
    tag_names = {t.name for t in tag_rows}
    assert len(tag_names) > 0


@pytest.mark.asyncio
async def test_process_article_returns_true_when_llm_returns_none(async_db_session):
    from models.article import Article
    from models.analysis import Analysis

    event = _make_event()
    llm = _mock_llm(result=None, use_default=False)

    # Handler returns True because the article was saved (outcome=NEW),
    # even though LLM analysis subsequently failed inside the event chain
    result = await _wire_pipeline_and_handle(async_db_session, llm, event)

    assert result is True
    article = (await async_db_session.execute(select(Article).filter_by(url=event.url))).scalars().first()
    assert article is not None
    analysis = (await async_db_session.execute(select(Analysis).filter_by(article_id=article.id))).scalars().first()
    assert analysis is None
