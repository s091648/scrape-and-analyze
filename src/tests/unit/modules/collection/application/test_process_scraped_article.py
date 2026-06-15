from unittest.mock import MagicMock

from src.modules.collection.application.use_cases import ArticleOutcome, ProcessScrapedArticleUseCase
from src.modules.collection.application.events import ArticleScrapedEvent
from src.shared.domain.entities import Article


def _make_event(source="rss", **kwargs):
    defaults = dict(url="https://example.com/article", title="T", content="C", source=source)
    defaults.update(kwargs)
    return ArticleScrapedEvent(**defaults)


def _make_article(source="rss"):
    return Article(url="https://example.com/article", url_hash="a" * 64, source=source, title="T", content="C")


def _make_uc(dedup, repo):
    return ProcessScrapedArticleUseCase(
        article_repo=repo,
        dedup_service=dedup,
    )


def test_execute_returns_new_outcome_and_article_for_unknown_url():
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = MagicMock()
    repo.save.return_value = article

    outcome, result = _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.NEW
    assert result is article


def test_execute_returns_failed_outcome_when_save_raises():
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    repo = MagicMock()
    repo.save.side_effect = Exception("DB error")

    outcome, result = _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.FAILED
    assert result is None


def test_execute_returns_duplicate_outcome_for_analyzed_article():
    article = _make_article()
    dedup = MagicMock()
    dedup.find_existing.return_value = article
    dedup.needs_analysis.return_value = False
    repo = MagicMock()

    outcome, result = _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.DUPLICATE
    assert result is None
    repo.save.assert_not_called()


def test_execute_returns_duplicate_needs_analysis_for_un_analyzed_article():
    article = _make_article()
    dedup = MagicMock()
    dedup.find_existing.return_value = article
    dedup.needs_analysis.return_value = True
    repo = MagicMock()

    outcome, result = _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS
    assert result is article
    repo.save.assert_not_called()
