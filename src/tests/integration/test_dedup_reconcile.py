"""
Integration tests for ArticleDedupRepository (SqlAlchemyArticleDedupRepository)
and its find_pending_reconciliation() candidate query.

src/tests/unit/infrastructure/persistence/collection/test_article_dedup_repo_impl.py
mocks the session entirely — it can't catch a wrong ON CONFLICT DO UPDATE
arithmetic expression, a JSONB operator typo, or the raw SQL in
_PENDING_RECONCILIATION_QUERY drifting out of sync with the real `articles`
table. These tests exercise all of that against a real PostgreSQL database
instead.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.infrastructure.persistence.collection.article_dedup_repo_impl import (
    SqlAlchemyArticleDedupRepository,
)


def _make_article(db_session, *, work_id=None, doi=None, merged_into_id=None,
                   last_reconciled_at=None, url=None):
    from models.article import Article
    from src.modules.collection.domain.value_objects import UrlHash

    url = url or f"https://example.com/{uuid.uuid4()}"
    metadata = {}
    if work_id is not None:
        metadata["work_id"] = work_id
    if doi is not None:
        metadata["doi"] = doi

    article = Article(
        url=url,
        url_hash=UrlHash.generate_url_hash(url),
        source="openalex",
        title="Test Article",
        content="Test content",
        correlation_id=uuid.uuid4(),
        metadata_=metadata or None,
        merged_into_id=merged_into_id,
        last_reconciled_at=last_reconciled_at,
    )
    db_session.add(article)
    db_session.commit()
    return article


def _make_repo(db_session):
    return SqlAlchemyArticleDedupRepository(db_session)


# ---------------------------------------------------------------------------
# find_by_work_id
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_find_by_work_id_returns_id_when_present(db_session):
    article = _make_article(db_session, work_id="W111")
    repo = _make_repo(db_session)

    assert repo.find_by_work_id("W111") == article.id


@pytest.mark.integration
def test_find_by_work_id_returns_none_when_absent(db_session):
    repo = _make_repo(db_session)
    assert repo.find_by_work_id("W-does-not-exist") is None


@pytest.mark.integration
def test_find_by_work_id_excludes_tombstoned_articles(db_session):
    survivor = _make_article(db_session, work_id="W222-survivor")
    _make_article(db_session, work_id="W222", merged_into_id=survivor.id)
    repo = _make_repo(db_session)

    # The tombstoned loser must not shadow a fresh lookup for its old work_id.
    assert repo.find_by_work_id("W222") is None


# ---------------------------------------------------------------------------
# heal_identifiers
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_heal_identifiers_persists_new_work_id_and_doi(db_session):
    from models.article import Article

    article = _make_article(db_session, work_id="OLD-ID")
    repo = _make_repo(db_session)

    repo.heal_identifiers(article.id, "NEW-ID", "10.1234/new-doi")

    reloaded = db_session.query(Article).filter_by(id=article.id).first()
    assert reloaded.metadata_["work_id"] == "NEW-ID"
    assert reloaded.metadata_["doi"] == "10.1234/new-doi"
    assert reloaded.last_reconciled_at is not None


@pytest.mark.integration
def test_heal_identifiers_keeps_existing_doi_when_none_given(db_session):
    from models.article import Article

    article = _make_article(db_session, work_id="OLD-ID", doi="10.1234/keep-me")
    repo = _make_repo(db_session)

    repo.heal_identifiers(article.id, "NEW-ID", None)

    reloaded = db_session.query(Article).filter_by(id=article.id).first()
    assert reloaded.metadata_["work_id"] == "NEW-ID"
    assert reloaded.metadata_["doi"] == "10.1234/keep-me"


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_merge_rolls_up_view_count_into_existing_metrics_row(db_session):
    from models.article import Article
    from models.article_metrics import ArticleMetrics

    loser = _make_article(db_session, work_id="LOSER-1")
    survivor = _make_article(db_session, work_id="SURVIVOR-1")
    db_session.add_all([
        ArticleMetrics(article_id=loser.id, view_count=5),
        ArticleMetrics(article_id=survivor.id, view_count=10),
    ])
    db_session.commit()

    repo = _make_repo(db_session)
    repo.merge(loser_id=loser.id, survivor_id=survivor.id)

    survivor_metrics = db_session.query(ArticleMetrics).filter_by(article_id=survivor.id).first()
    assert survivor_metrics.view_count == 15

    reloaded_loser = db_session.query(Article).filter_by(id=loser.id).first()
    assert reloaded_loser.merged_into_id == survivor.id


@pytest.mark.integration
def test_merge_creates_metrics_row_when_survivor_has_none(db_session):
    from models.article_metrics import ArticleMetrics

    loser = _make_article(db_session, work_id="LOSER-2")
    survivor = _make_article(db_session, work_id="SURVIVOR-2")
    db_session.add(ArticleMetrics(article_id=loser.id, view_count=7))
    db_session.commit()

    repo = _make_repo(db_session)
    repo.merge(loser_id=loser.id, survivor_id=survivor.id)

    survivor_metrics = db_session.query(ArticleMetrics).filter_by(article_id=survivor.id).first()
    assert survivor_metrics is not None
    assert survivor_metrics.view_count == 7


@pytest.mark.integration
def test_merge_skips_view_count_rollup_when_loser_has_no_views(db_session):
    from models.article_metrics import ArticleMetrics

    loser = _make_article(db_session, work_id="LOSER-3")
    survivor = _make_article(db_session, work_id="SURVIVOR-3")
    db_session.add(ArticleMetrics(article_id=loser.id, view_count=0))
    db_session.commit()

    repo = _make_repo(db_session)
    repo.merge(loser_id=loser.id, survivor_id=survivor.id)

    # No metrics row should have been fabricated for the survivor.
    assert db_session.query(ArticleMetrics).filter_by(article_id=survivor.id).first() is None


@pytest.mark.integration
def test_merge_unions_loser_tags_into_survivor_without_duplicates(db_session):
    from models.tag import Tag, article_tags

    loser = _make_article(db_session, work_id="LOSER-4")
    survivor = _make_article(db_session, work_id="SURVIVOR-4")

    tag_only_on_loser = Tag(name=f"loser-only-{uuid.uuid4().hex[:8]}")
    tag_on_both = Tag(name=f"shared-{uuid.uuid4().hex[:8]}")
    db_session.add_all([tag_only_on_loser, tag_on_both])
    db_session.flush()

    db_session.execute(article_tags.insert().values([
        {"article_id": loser.id, "tag_id": tag_only_on_loser.id},
        {"article_id": loser.id, "tag_id": tag_on_both.id},
        {"article_id": survivor.id, "tag_id": tag_on_both.id},
    ]))
    db_session.commit()

    repo = _make_repo(db_session)
    repo.merge(loser_id=loser.id, survivor_id=survivor.id)  # must not raise a duplicate-key error

    survivor_tag_ids = {
        row.tag_id for row in
        db_session.query(article_tags.c.tag_id).filter(article_tags.c.article_id == survivor.id)
    }
    assert survivor_tag_ids == {tag_only_on_loser.id, tag_on_both.id}


@pytest.mark.integration
def test_merge_never_deletes_either_article_row(db_session):
    from models.article import Article

    loser = _make_article(db_session, work_id="LOSER-5")
    survivor = _make_article(db_session, work_id="SURVIVOR-5")

    repo = _make_repo(db_session)
    repo.merge(loser_id=loser.id, survivor_id=survivor.id)

    assert db_session.query(Article).filter_by(id=loser.id).first() is not None
    assert db_session.query(Article).filter_by(id=survivor.id).first() is not None


@pytest.mark.integration
def test_merge_tombstones_loser_not_survivor(db_session):
    from models.article import Article

    loser = _make_article(db_session, work_id="LOSER-6")
    survivor = _make_article(db_session, work_id="SURVIVOR-6")

    repo = _make_repo(db_session)
    repo.merge(loser_id=loser.id, survivor_id=survivor.id)

    reloaded_loser = db_session.query(Article).filter_by(id=loser.id).first()
    reloaded_survivor = db_session.query(Article).filter_by(id=survivor.id).first()
    assert reloaded_loser.merged_into_id == survivor.id
    assert reloaded_loser.merged_at is not None
    assert reloaded_survivor.merged_into_id is None


# ---------------------------------------------------------------------------
# mark_reconciled
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_mark_reconciled_sets_timestamp(db_session):
    from models.article import Article

    article = _make_article(db_session, work_id="CANONICAL-1")
    assert article.last_reconciled_at is None

    repo = _make_repo(db_session)
    repo.mark_reconciled(article.id)

    reloaded = db_session.query(Article).filter_by(id=article.id).first()
    assert reloaded.last_reconciled_at is not None


# ---------------------------------------------------------------------------
# find_pending_reconciliation
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_find_pending_reconciliation_selects_the_right_candidates(db_session):
    now = datetime.now(timezone.utc)
    never_checked = _make_article(db_session, work_id="PENDING-NEVER-CHECKED")
    stale = _make_article(db_session, work_id="PENDING-STALE",
                           last_reconciled_at=now - timedelta(days=10))
    recently_checked = _make_article(db_session, work_id="PENDING-RECENT",
                                      last_reconciled_at=now - timedelta(hours=1))
    already_merged = _make_article(db_session, work_id="PENDING-MERGED",
                                    merged_into_id=never_checked.id)
    no_work_id = _make_article(db_session)

    repo = _make_repo(db_session)
    candidates = repo.find_pending_reconciliation(limit=100)
    ids = {c.article_id for c in candidates}

    assert never_checked.id in ids
    assert stale.id in ids
    assert recently_checked.id not in ids
    assert already_merged.id not in ids
    assert no_work_id.id not in ids


@pytest.mark.integration
def test_find_pending_reconciliation_respects_limit(db_session):
    for i in range(3):
        _make_article(db_session, work_id=f"LIMIT-TEST-{i}")

    repo = _make_repo(db_session)
    candidates = repo.find_pending_reconciliation(limit=2)
    assert len(candidates) == 2
