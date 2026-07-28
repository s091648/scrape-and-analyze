"""
Unit tests for SqlAlchemyArticleDedupRepository — covers the write-side of
OpenAlex dedup reconciliation: identifier healing, view_count/tag rollup, and
the merged_into_id tombstone. Merging never deletes a row (see
alembic/versions/25_add_article_merge_tombstone.py for why), so these tests
assert what gets rolled up/updated, never a delete call.
"""
from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from src.infrastructure.persistence.collection.article_dedup_repo_impl import SqlAlchemyArticleDedupRepository


def _make_tag_row(tag_id):
    row = MagicMock()
    row.tag_id = tag_id
    return row


def _mock_merge_queries(session, loser_metrics=None, loser_tag_ids=(), survivor_tag_ids=()):
    """Wire session.query(...) call order to match SqlAlchemyArticleDedupRepository.merge():
    1) ArticleMetrics.filter_by(...).first()  2) loser tag ids  3) survivor tag ids
    4) Article.filter_by(...).update(...)"""
    metrics_query = MagicMock()
    metrics_query.filter_by.return_value.first.return_value = loser_metrics

    loser_tags_query = MagicMock()
    loser_tags_query.filter.return_value = iter([_make_tag_row(t) for t in loser_tag_ids])

    survivor_tags_query = MagicMock()
    survivor_tags_query.filter.return_value = iter([_make_tag_row(t) for t in survivor_tag_ids])

    update_query = MagicMock()

    session.query.side_effect = [metrics_query, loser_tags_query, survivor_tags_query, update_query]
    return update_query


# ---------------------------------------------------------------------------
# find_by_work_id
# ---------------------------------------------------------------------------

def test_find_by_work_id_returns_id_when_found():
    session = MagicMock()
    found_id = uuid4()
    row = MagicMock()
    row.id = found_id
    session.execute.return_value.first.return_value = row

    repo = SqlAlchemyArticleDedupRepository(session=session)
    result = repo.find_by_work_id("https://openalex.org/W999")

    assert result == found_id


def test_find_by_work_id_returns_none_when_not_found():
    session = MagicMock()
    session.execute.return_value.first.return_value = None

    repo = SqlAlchemyArticleDedupRepository(session=session)
    result = repo.find_by_work_id("https://openalex.org/W999")

    assert result is None


# ---------------------------------------------------------------------------
# heal_identifiers
# ---------------------------------------------------------------------------

def test_heal_identifiers_updates_work_id_and_doi():
    session = MagicMock()
    article = MagicMock()
    article.metadata_ = {"work_id": "https://openalex.org/Wold", "doi": "10.1/old"}
    session.query.return_value.filter_by.return_value.first.return_value = article

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.heal_identifiers(uuid4(), "https://openalex.org/Wnew", "10.1/new")

    assert article.metadata_["work_id"] == "https://openalex.org/Wnew"
    assert article.metadata_["doi"] == "10.1/new"
    assert isinstance(article.last_reconciled_at, datetime)
    session.commit.assert_called_once()


def test_heal_identifiers_keeps_existing_doi_when_none_given():
    session = MagicMock()
    article = MagicMock()
    article.metadata_ = {"work_id": "https://openalex.org/Wold", "doi": "10.1/old"}
    session.query.return_value.filter_by.return_value.first.return_value = article

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.heal_identifiers(uuid4(), "https://openalex.org/Wnew", None)

    assert article.metadata_["doi"] == "10.1/old"


def test_heal_identifiers_noop_when_article_not_found():
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.heal_identifiers(uuid4(), "https://openalex.org/Wnew", "10.1/new")

    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

def test_merge_rolls_up_view_count_when_loser_has_views():
    session = MagicMock()
    loser_id, survivor_id = uuid4(), uuid4()
    loser_metrics = MagicMock()
    loser_metrics.view_count = 7
    _mock_merge_queries(session, loser_metrics=loser_metrics)

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.merge(loser_id=loser_id, survivor_id=survivor_id)

    # Exactly one execute(): the ArticleMetrics view_count upsert.
    assert session.execute.call_count == 1
    session.commit.assert_called_once()


def test_merge_skips_view_count_rollup_when_loser_has_no_metrics_row():
    session = MagicMock()
    loser_id, survivor_id = uuid4(), uuid4()
    _mock_merge_queries(session, loser_metrics=None)

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.merge(loser_id=loser_id, survivor_id=survivor_id)

    assert session.execute.call_count == 0


def test_merge_skips_view_count_rollup_when_loser_view_count_is_zero():
    session = MagicMock()
    loser_id, survivor_id = uuid4(), uuid4()
    loser_metrics = MagicMock()
    loser_metrics.view_count = 0
    _mock_merge_queries(session, loser_metrics=loser_metrics)

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.merge(loser_id=loser_id, survivor_id=survivor_id)

    assert session.execute.call_count == 0


def test_merge_unions_only_tags_missing_from_survivor():
    session = MagicMock()
    loser_id, survivor_id = uuid4(), uuid4()
    shared_tag = uuid4()
    loser_only_tag = uuid4()
    _mock_merge_queries(
        session,
        loser_tag_ids=[shared_tag, loser_only_tag],
        survivor_tag_ids=[shared_tag],
    )

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.merge(loser_id=loser_id, survivor_id=survivor_id)

    # Only the one tag missing from the survivor gets inserted.
    assert session.execute.call_count == 1


def test_merge_inserts_nothing_when_tags_already_identical():
    session = MagicMock()
    loser_id, survivor_id = uuid4(), uuid4()
    shared_tag = uuid4()
    _mock_merge_queries(session, loser_tag_ids=[shared_tag], survivor_tag_ids=[shared_tag])

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.merge(loser_id=loser_id, survivor_id=survivor_id)

    assert session.execute.call_count == 0


def test_merge_tombstones_the_loser_not_the_survivor():
    session = MagicMock()
    loser_id, survivor_id = uuid4(), uuid4()
    update_query = _mock_merge_queries(session)

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.merge(loser_id=loser_id, survivor_id=survivor_id)

    update_query.filter_by.assert_called_once_with(id=loser_id)
    update_fields = update_query.filter_by.return_value.update.call_args[0][0]
    assert update_fields["merged_into_id"] == survivor_id
    assert isinstance(update_fields["merged_at"], datetime)
    assert isinstance(update_fields["last_reconciled_at"], datetime)
    session.commit.assert_called_once()


def test_merge_never_calls_delete():
    """Merging must never delete a row — several FKs into `articles` (analyses,
    article_tags, failed_tasks) have no ON DELETE action, and deletion would
    also make the merge irreversible if the dedup decision turned out wrong."""
    session = MagicMock()
    _mock_merge_queries(session)

    repo = SqlAlchemyArticleDedupRepository(session=session)
    repo.merge(loser_id=uuid4(), survivor_id=uuid4())

    session.delete.assert_not_called()


# ---------------------------------------------------------------------------
# mark_reconciled
# ---------------------------------------------------------------------------

def test_mark_reconciled_updates_timestamp_and_commits():
    session = MagicMock()
    update_query = MagicMock()
    session.query.return_value = update_query

    repo = SqlAlchemyArticleDedupRepository(session=session)
    article_id = uuid4()
    repo.mark_reconciled(article_id)

    update_query.filter_by.assert_called_once_with(id=article_id)
    update_fields = update_query.filter_by.return_value.update.call_args[0][0]
    assert isinstance(update_fields["last_reconciled_at"], datetime)
    session.commit.assert_called_once()
