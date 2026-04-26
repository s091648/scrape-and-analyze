import uuid
from unittest.mock import MagicMock
import pytest
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.collection.application.dtos import ScrapedArticleDTO
from src.modules.collection.application.use_cases import ArticleOutcome


def _make_result():
    content = AnalysisContent(tag_groups=[], pain_points="p", insights="i",
                               innovations="n", summary="s")
    metadata = AnalysisMetadata(model_used="test-model", input_tokens=10, output_tokens=5)
    return (content, metadata)


def _wire_pipeline(db_session):
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.shared.topic_repo_impl import SqlAlchemyTopicRepository
    from src.infrastructure.shared.events.in_memory_event_bus import InMemoryEventBus
    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
    from src.modules.intelligence.application.use_cases.analyze_article import AnalyzeArticleUseCase
    from src.modules.intelligence.application.event_handlers import ArticleProcessedHandler
    from src.shared.application.events import ArticleProcessedEvent

    llm = MagicMock()
    llm.analyze.return_value = _make_result()

    article_repo = SqlAlchemyArticleRepository(session=db_session)
    analysis_repo = SqlAlchemyAnalysisRepository(session=db_session)
    topic_repo = SqlAlchemyTopicRepository(session=db_session)
    event_bus = InMemoryEventBus()

    process_uc = ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=DedupService(article_repo=article_repo),
        event_bus=event_bus,
    )
    analyze_uc = AnalyzeArticleUseCase(
        llm_service=llm,
        analysis_repository=analysis_repo,
        topic_repository=topic_repo,
    )
    handler = ArticleProcessedHandler(use_case=analyze_uc)
    event_bus.subscribe(ArticleProcessedEvent, handler.handle)
    return process_uc


@pytest.mark.integration
def test_article_gets_topic_id_on_save(db_session, test_topic):
    from models.article import Article
    topic_id = test_topic
    event = ScrapedArticleDTO(
        url=f"https://example.com/{uuid.uuid4()}",
        title="Test Article", content="Body.", source="rss",
        topic_id=topic_id,
    )
    uc = _wire_pipeline(db_session)
    result = uc.execute(event)
    assert result == ArticleOutcome.NEW
    article = db_session.query(Article).filter_by(url=event.url).first()
    assert article is not None
    assert article.topic_id == topic_id