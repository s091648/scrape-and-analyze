from unittest.mock import MagicMock
from uuid import uuid4
from src.domain.entities.article import ArticleEntity


def _article(**overrides):
    defaults = dict(
        id=uuid4(), url="https://arxiv.org/abs/x", url_hash="abc",
        source="arxiv", title="T", content="Abstract.", correlation_id=uuid4(),
    )
    defaults.update(overrides)
    return ArticleEntity(**defaults)


def test_prepare_content_uses_sections_for_arxiv():
    from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
    uc = AnalyzeArticleUseCase(analyzer=MagicMock(), analysis_repo=MagicMock())
    article = _article(metadata={"sections": {"introduction": "Intro.", "conclusion": "Concl."}})
    result = uc._prepare_content(article)
    assert "Introduction" in result
    assert "Intro." in result


def test_prepare_content_falls_back_to_abstract_when_no_sections():
    from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
    uc = AnalyzeArticleUseCase(analyzer=MagicMock(), analysis_repo=MagicMock())
    article = _article(metadata={"abstract": "Fallback abstract.", "sections": {}})
    result = uc._prepare_content(article)
    assert result == "Fallback abstract."


def test_prepare_content_returns_content_for_non_arxiv():
    from src.app.use_cases.analyze_article import AnalyzeArticleUseCase
    uc = AnalyzeArticleUseCase(analyzer=MagicMock(), analysis_repo=MagicMock())
    article = _article(source="blog", url="https://blog.example.com/post",
                       content="Blog body.", metadata={})
    result = uc._prepare_content(article)
    assert result == "Blog body."
