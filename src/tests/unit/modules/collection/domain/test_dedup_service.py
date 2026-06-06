from unittest.mock import MagicMock

from src.modules.collection.domain.services import DedupService
from src.shared.domain.entities import Article


def _make_article():
    return Article(url="https://example.com/a", url_hash="a" * 64, source="rss", title="T", content="C")


# ---------------------------------------------------------------------------
# find_existing
# ---------------------------------------------------------------------------

def test_find_existing_returns_none_for_unknown_url():
    repo = MagicMock()
    repo.find_by_url_hash.return_value = None
    svc = DedupService(article_repo=repo)
    assert svc.find_existing("https://example.com/new") is None


def test_find_existing_returns_article_for_known_url():
    article = _make_article()
    repo = MagicMock()
    repo.find_by_url_hash.return_value = article
    svc = DedupService(article_repo=repo)
    assert svc.find_existing("https://example.com/a") is article


# ---------------------------------------------------------------------------
# needs_analysis
# ---------------------------------------------------------------------------

def test_needs_analysis_returns_false_when_article_has_analysis():
    article = _make_article()
    repo = MagicMock()
    repo.has_analysis.return_value = True
    svc = DedupService(article_repo=repo)
    assert svc.needs_analysis(article) is False


def test_needs_analysis_returns_true_when_article_has_no_analysis():
    article = _make_article()
    repo = MagicMock()
    repo.has_analysis.return_value = False
    svc = DedupService(article_repo=repo)
    assert svc.needs_analysis(article) is True


def test_needs_analysis_returns_false_for_unsaved_article():
    article = _make_article()
    article.id = None
    repo = MagicMock()
    svc = DedupService(article_repo=repo)
    assert svc.needs_analysis(article) is False
    repo.has_analysis.assert_not_called()
