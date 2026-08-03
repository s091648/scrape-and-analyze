from unittest.mock import MagicMock
from uuid import uuid4

from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository
from src.modules.collection.domain.repositories.article_metrics_repository import StaleArticle


# ---------------------------------------------------------------------------
# find_stale
# ---------------------------------------------------------------------------

def test_find_stale_maps_rows_to_dataclasses():
    session = MagicMock()
    article_id = uuid4()
    row = MagicMock()
    row.id = article_id
    row.metadata = {"doi": "10.1234/a"}
    session.execute.return_value.fetchall.return_value = [row]

    repo = SqlAlchemyArticleMetricsRepository(session=session)
    result = repo.find_stale(["citation_count"], limit=100)

    assert result == [StaleArticle(article_id=article_id, metadata={"doi": "10.1234/a"})]


def test_find_stale_passes_metric_keys_and_limit_params():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    repo = SqlAlchemyArticleMetricsRepository(session=session)
    repo.find_stale(["citation_count", "impact_factor"], limit=42)

    args, kwargs = session.execute.call_args
    assert args[1]["metric_keys"] == ["citation_count", "impact_factor"]
    assert args[1]["limit"] == 42


def test_find_stale_defaults_null_metadata_to_empty_dict():
    session = MagicMock()
    article_id = uuid4()
    row = MagicMock()
    row.id = article_id
    row.metadata = None
    session.execute.return_value.fetchall.return_value = [row]

    repo = SqlAlchemyArticleMetricsRepository(session=session)
    result = repo.find_stale(["citation_count"], limit=100)

    assert result == [StaleArticle(article_id=article_id, metadata={})]


def test_upsert_always_ensures_article_metrics_row():
    session = MagicMock()
    repo = SqlAlchemyArticleMetricsRepository(session=session)
    article_id = uuid4()

    repo.upsert(article_id, {})

    # First execute() call is the article_metrics ON CONFLICT DO NOTHING insert,
    # even when metrics is empty — every article gets a row for view_count tracking.
    assert session.execute.call_count == 1
    session.commit.assert_called_once()


def test_upsert_writes_one_row_per_metric_key():
    session = MagicMock()
    repo = SqlAlchemyArticleMetricsRepository(session=session)
    article_id = uuid4()

    repo.upsert(article_id, {"citation_count": 42, "impact_factor": 4.5})

    # 1 article_metrics insert + 2 article_metric_values inserts (one per key)
    assert session.execute.call_count == 3
    session.commit.assert_called_once()


def test_upsert_with_single_metric():
    session = MagicMock()
    repo = SqlAlchemyArticleMetricsRepository(session=session)
    article_id = uuid4()

    repo.upsert(article_id, {"citation_count": 10})

    assert session.execute.call_count == 2
    session.commit.assert_called_once()
