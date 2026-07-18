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


def _make_uc(dedup, repo, metrics_repo=None):
    return ProcessScrapedArticleUseCase(
        article_repo=repo,
        dedup_service=dedup,
        article_metrics_repo=metrics_repo,
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


# ─── article_metrics upsert ──────────────────────────────────────────────────

def test_article_metrics_upsert_called_with_citation_count():
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = MagicMock()
    repo.save.return_value = article
    metrics_repo = MagicMock()

    event = _make_event(metadata={"citation_count": 42})
    _make_uc(dedup, repo, metrics_repo).execute(event)

    metrics_repo.upsert.assert_called_once_with(article.id, {"citation_count": 42})


def test_article_metrics_upsert_called_with_empty_dict_when_missing():
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = MagicMock()
    repo.save.return_value = article
    metrics_repo = MagicMock()

    _make_uc(dedup, repo, metrics_repo).execute(_make_event())

    metrics_repo.upsert.assert_called_once_with(article.id, {})


def test_article_metrics_upsert_ignores_unknown_metadata_keys():
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = MagicMock()
    repo.save.return_value = article
    metrics_repo = MagicMock()

    event = _make_event(metadata={"citation_count": 5, "some_other_field": "ignored"})
    _make_uc(dedup, repo, metrics_repo).execute(event)

    metrics_repo.upsert.assert_called_once_with(article.id, {"citation_count": 5})


def test_article_metrics_not_called_when_repo_absent():
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = MagicMock()
    repo.save.return_value = article

    outcome, _ = _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.NEW


def test_article_metrics_upsert_failure_does_not_fail_use_case():
    dedup = MagicMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = MagicMock()
    repo.save.return_value = article
    metrics_repo = MagicMock()
    metrics_repo.upsert.side_effect = Exception("DB error")

    outcome, result = _make_uc(dedup, repo, metrics_repo).execute(_make_event())

    assert outcome == ArticleOutcome.NEW
    assert result is article
