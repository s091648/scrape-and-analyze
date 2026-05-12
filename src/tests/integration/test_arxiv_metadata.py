import uuid
from unittest.mock import MagicMock
import pytest
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ArticleOutcome


def _make_result():
    return AnalysisContent(pain_points=None,
        insights=None,
        innovations=None,
        summary=None,
        tag_groups=None
    ), AnalysisMetadata(model_used="test-model",
    input_tokens=10,
    output_tokens=5)


def _make_uc(db_session):
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.intelligence.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.infrastructure.persistence.collection.arxiv_metadata_repo_impl import SqlAlchemyArxivMetadataRepository
    from src.modules.collection.domain.services import DedupService
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase
    from src.infrastructure.shared.events import InMemoryEventBus
    analyzer = MagicMock()
    analyzer.analyze.return_value = _make_result()
    return ProcessScrapedArticleUseCase(
        article_repo=SqlAlchemyArticleRepository(session=db_session),
        dedup_service=DedupService(article_repo=SqlAlchemyArticleRepository(session=db_session)),
        event_bus=InMemoryEventBus(),
        arxiv_metadata_repo=SqlAlchemyArxivMetadataRepository(session=db_session),
    )


@pytest.mark.integration
def test_arxiv_article_creates_arxiv_metadata_row(db_session):
    from models.arxiv_metadata import ArxivMetadata
    from models.article import Article
    scraped = ArticleScrapedEvent(
        url=f"https://arxiv.org/abs/{uuid.uuid4()}v1",
        title="Test Paper", content="Abstract.", published_at="2024-01-01",
        source="arxiv",
        topic_id=None,
        metadata={
            "authors": ["Alice", "Bob"], "arxiv_id": "2601.00001",
            "abstract": "Abstract.", "pdf_available": True,
            "sections": {"introduction": "Intro.", "conclusion": "Conc."},
        },
    )
    uc = _make_uc(db_session)
    result = uc.execute(scraped)
    assert result == ArticleOutcome.NEW
    article = db_session.query(Article).filter_by(url=scraped.url).first()
    assert article is not None
    meta = db_session.query(ArxivMetadata).filter_by(article_id=article.id).first()
    assert meta is not None
    assert meta.authors == ["Alice", "Bob"]
    assert meta.pdf_available is True
    assert meta.sections == {"introduction": "Intro.", "conclusion": "Conc."}