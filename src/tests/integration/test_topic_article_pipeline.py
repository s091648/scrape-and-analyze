import uuid
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome


def _make_result():
    content = AnalysisContent(tag_groups=[], pain_points="p", insights="i",
                               innovations="n", summary="s")
    metadata = AnalysisMetadata(model_used="test-model", input_tokens=10, output_tokens=5)
    return (content, metadata)


async def _wire_pipeline(async_db_session):
    from src.infrastructure.persistence.shared.article_async_repo_impl import AsyncSqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_async_repo_impl import AsyncSqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_async_repo_impl import AsyncSqlAlchemyTopicRepository
    from src.infrastructure.persistence.intelligence.tag_group_definition_async_repo_impl import AsyncSqlAlchemyTagGroupDefinitionRepository
    from src.infrastructure.shared.events.in_memory_event_bus import AsyncInMemoryEventBus
    from src.modules.collection.domain.services import AsyncDedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler
    from src.modules.intelligence.domain.value_objects import AnalysisPrompt
    from src.shared.application.events import ArticleProcessedEvent

    llm = AsyncMock()
    llm.analyze.return_value = _make_result()

    article_repo = AsyncSqlAlchemyArticleRepository(session=async_db_session)
    analysis_repo = AsyncSqlAlchemyAnalysisRepository(session=async_db_session)
    topic_repo = AsyncSqlAlchemyTopicRepository(session=async_db_session)
    tag_group_def_repo = AsyncSqlAlchemyTagGroupDefinitionRepository(session=async_db_session)
    event_bus = AsyncInMemoryEventBus()

    process_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=AsyncDedupService(article_repo=article_repo),
    )
    analyze_uc = AnalyzeArticleUseCase(
        llm_service=llm,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
        tag_group_definition_repository=tag_group_def_repo,
        prompt=AnalysisPrompt(),
    )
    handler = ArticleProcessedHandler(use_case=analyze_uc, event_bus=event_bus)
    await event_bus.subscribe(ArticleProcessedEvent, handler.handle)
    return process_uc


@pytest.mark.integration
@pytest.mark.asyncio
async def test_article_gets_topic_id_on_save(async_db_session, test_topic):
    from models.article import Article
    topic_id = test_topic
    event = ArticleScrapedEvent(
        url=f"https://example.com/{uuid.uuid4()}",
        title="Test Article", content="Body.", source="rss",
        topic_id=topic_id,
    )
    uc = await _wire_pipeline(async_db_session)
    outcome, _ = await uc.execute(event)
    assert outcome == ArticleOutcome.NEW
    article = (await async_db_session.execute(select(Article).filter_by(url=event.url))).scalars().first()
    assert article is not None
    assert article.topic_id == topic_id
