from unittest.mock import AsyncMock

import pytest

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


@pytest.mark.asyncio
async def test_execute_returns_new_outcome_and_article_for_unknown_url():
    dedup = AsyncMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = AsyncMock()
    repo.save.return_value = article

    outcome, result = await _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.NEW
    assert result is article


@pytest.mark.asyncio
async def test_execute_returns_failed_outcome_when_save_raises():
    dedup = AsyncMock()
    dedup.find_existing.return_value = None
    repo = AsyncMock()
    repo.save.side_effect = Exception("DB error")

    outcome, result = await _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.FAILED
    assert result is None


@pytest.mark.asyncio
async def test_execute_returns_duplicate_outcome_for_analyzed_article():
    article = _make_article()
    dedup = AsyncMock()
    dedup.find_existing.return_value = article
    dedup.needs_analysis.return_value = False
    repo = AsyncMock()

    outcome, result = await _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.DUPLICATE
    assert result is None
    repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_execute_returns_duplicate_needs_analysis_for_un_analyzed_article():
    article = _make_article()
    dedup = AsyncMock()
    dedup.find_existing.return_value = article
    dedup.needs_analysis.return_value = True
    repo = AsyncMock()

    outcome, result = await _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS
    assert result is article
    repo.save.assert_not_called()


# ─── article_metrics upsert ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_article_metrics_upsert_called_with_citation_count():
    dedup = AsyncMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = AsyncMock()
    repo.save.return_value = article
    metrics_repo = AsyncMock()

    event = _make_event(metadata={"citation_count": 42})
    await _make_uc(dedup, repo, metrics_repo).execute(event)

    metrics_repo.upsert.assert_called_once_with(article.id, {"citation_count": 42})


@pytest.mark.asyncio
async def test_article_metrics_upsert_called_with_empty_dict_when_missing():
    dedup = AsyncMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = AsyncMock()
    repo.save.return_value = article
    metrics_repo = AsyncMock()

    await _make_uc(dedup, repo, metrics_repo).execute(_make_event())

    metrics_repo.upsert.assert_called_once_with(article.id, {})


@pytest.mark.asyncio
async def test_article_metrics_upsert_ignores_unknown_metadata_keys():
    dedup = AsyncMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = AsyncMock()
    repo.save.return_value = article
    metrics_repo = AsyncMock()

    event = _make_event(metadata={"citation_count": 5, "some_other_field": "ignored"})
    await _make_uc(dedup, repo, metrics_repo).execute(event)

    metrics_repo.upsert.assert_called_once_with(article.id, {"citation_count": 5})


@pytest.mark.asyncio
async def test_article_metrics_not_called_when_repo_absent():
    dedup = AsyncMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = AsyncMock()
    repo.save.return_value = article

    outcome, _ = await _make_uc(dedup, repo).execute(_make_event())

    assert outcome == ArticleOutcome.NEW


@pytest.mark.asyncio
async def test_article_metrics_upsert_failure_does_not_fail_use_case():
    dedup = AsyncMock()
    dedup.find_existing.return_value = None
    article = _make_article()
    repo = AsyncMock()
    repo.save.return_value = article
    metrics_repo = AsyncMock()
    metrics_repo.upsert.side_effect = Exception("DB error")

    outcome, result = await _make_uc(dedup, repo, metrics_repo).execute(_make_event())

    assert outcome == ArticleOutcome.NEW
    assert result is article
