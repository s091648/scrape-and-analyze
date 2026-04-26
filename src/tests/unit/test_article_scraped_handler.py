from unittest.mock import MagicMock
from src.modules.collection.application.use_cases import ArticleOutcome, PipelineStats
from src.modules.collection.application.dtos import ScrapedArticleDTO


def _make_dto(source="arxiv") -> ScrapedArticleDTO:
    return ScrapedArticleDTO(url="https://example.com", title="T", content="C", source=source)


def test_handle_new_article_records_new_and_returns_true():
    from src.modules.collection.application.event_handlers.article_scraped_handler import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = ArticleOutcome.NEW
    stats = PipelineStats()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats)
    result = handler.handle(_make_dto("arxiv"))

    assert result is True
    assert stats.get_results()[0].new == 1
    assert stats.get_results()[0].duplicate == 0


def test_handle_duplicate_article_records_duplicate_and_returns_true():
    from src.modules.collection.application.event_handlers.article_scraped_handler import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = ArticleOutcome.DUPLICATE
    stats = PipelineStats()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats)
    result = handler.handle(_make_dto("rss"))

    assert result is True
    assert stats.get_results()[0].duplicate == 1


def test_handle_failed_article_records_failed_and_returns_false():
    from src.modules.collection.application.event_handlers.article_scraped_handler import ArticleScrapedHandler
    use_case = MagicMock()
    use_case.execute.return_value = ArticleOutcome.FAILED
    stats = PipelineStats()

    handler = ArticleScrapedHandler(use_case=use_case, pipeline_stats=stats)
    result = handler.handle(_make_dto("blog"))

    assert result is False
    assert stats.get_results()[0].failed == 1