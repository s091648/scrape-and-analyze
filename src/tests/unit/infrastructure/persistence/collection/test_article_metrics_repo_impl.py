from unittest.mock import MagicMock
from uuid import uuid4

from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository


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
