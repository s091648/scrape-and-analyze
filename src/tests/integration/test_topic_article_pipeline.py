import uuid
from unittest.mock import MagicMock
import pytest
from src.analysis.providers.base_llm_provider import AnalysisResult
from src.ingestion.models.scraped_article import ScrapedArticle


def _make_result():
    return AnalysisResult(
        tag_groups=[], pain_points="p", insights="i",
        innovations="n", summary="s",
        input_tokens=10, output_tokens=5, model_used="test-model",
    )


def _make_uc(db_session):
    from src.infrastructure.persistence.sqlalchemy_repos.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.sqlalchemy_repos.analysis_repo_impl import SqlAlchemyAnalysisRepository
    from src.domain.services.dedup_service import DedupService
    from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
    from src.app.use_cases.process_article import ProcessArticleUseCase
    analyzer = MagicMock()
    analyzer.analyze.return_value = _make_result()
    return ProcessArticleUseCase(
        article_repo=SqlAlchemyArticleRepository(session=db_session),
        dedup_service=DedupService(article_repo=SqlAlchemyArticleRepository(session=db_session)),
        analyze_article_uc=AnalyzeArticleUseCase(
            analyzer=analyzer,
            analysis_repo=SqlAlchemyAnalysisRepository(session=db_session),
        ),
    )


@pytest.mark.integration
def test_article_gets_topic_id_on_save(db_session, test_topic):
    from models.article import Article
    topic_id = str(test_topic)
    scraped = ScrapedArticle(
        url=f"https://example.com/{uuid.uuid4()}",
        title="Test Article", content="Body.", published_at=None,
        source="rss", topic_id=topic_id,
    )
    uc = _make_uc(db_session)
    result = uc.execute(scraped, "test prompt", str(uuid.uuid4()))
    assert result is True
    article = db_session.query(Article).filter_by(url=scraped.url).first()
    assert article is not None
    assert str(article.topic_id) == topic_id
