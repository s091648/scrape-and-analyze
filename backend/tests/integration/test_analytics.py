"""Integration tests for the /admin/analytics page's data:

  GET /admin/analytics/overview          — trending / daily totals / by-topic / all-time top
  flush_view_counts()                    — now also writes collection.article_view_daily

Requires a real Postgres (the isolated backend_test schema) and, for the flush test, Redis.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from backend.tests.integration.conftest import admin_token, user_token

pytestmark = pytest.mark.integration
_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}


def _utc_today():
    return datetime.now(timezone.utc).date()


def _topic(db_session, name):
    from models.topic import Topic
    t = Topic(id=uuid.uuid4(), name=f"{name}-{uuid.uuid4().hex[:6]}", display_name=name)
    db_session.add(t)
    db_session.flush()
    return t


def _article(db_session, title, topic=None, original_source="Example Blog"):
    from models.article import Article
    a = Article(
        id=uuid.uuid4(),
        url=f"https://example.com/{uuid.uuid4().hex}",
        url_hash=uuid.uuid4().hex,
        source="rss",
        title=title,
        content="body",
        correlation_id=uuid.uuid4(),
        scraped_at=datetime.now(timezone.utc),
        topic_id=topic.id if topic else None,
        original_source=original_source,
    )
    db_session.add(a)
    db_session.flush()
    return a


def _views(db_session, article, day, views):
    from models.article_view_daily import ArticleViewDaily
    db_session.add(ArticleViewDaily(id=uuid.uuid4(), article_id=article.id, day=day, views=views))
    db_session.flush()


# ---------------------------------------------------------------------------
# GET /admin/analytics/overview
# ---------------------------------------------------------------------------

def test_overview_requires_admin(api_client):
    # require_admin has no guest-specific branch: a guest token has no `role` claim,
    # so it falls through the role check to 403, same as any other non-admin token.
    assert api_client.get("/admin/analytics/overview").status_code == 403  # default guest token
    assert api_client.get(
        "/admin/analytics/overview", headers={"Authorization": f"Bearer {user_token()}"}
    ).status_code == 403
    assert api_client.get(
        "/admin/analytics/overview", headers={"Authorization": ""}
    ).status_code == 401


def test_overview_trending_ordering_totals_and_sparkline(db_session, api_client):
    topic = _topic(db_session, "LLMs")
    hot = _article(db_session, "Hot article", topic)
    mild = _article(db_session, "Mild article", topic)
    today = _utc_today()
    _views(db_session, hot, today, 40)
    _views(db_session, hot, today - timedelta(days=1), 10)
    _views(db_session, mild, today, 5)
    db_session.commit()

    r = api_client.get("/admin/analytics/overview?days=30", headers=_ADMIN_HDR)
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 30

    titles = [t["title"] for t in body["trending"]]
    assert titles[:2] == ["Hot article", "Mild article"]  # 50 window views vs 5

    hot_row = body["trending"][0]
    assert hot_row["window_views"] == 50
    assert hot_row["topic"] == "LLMs"
    assert hot_row["source"] == "Example Blog"
    assert sum(p["views"] for p in hot_row["sparkline"]) == 50
    assert len(hot_row["sparkline"]) == 2  # two distinct days

    assert sum(d["views"] for d in body["daily_totals"]) == 55
    assert {row["topic"]: row["views"] for row in body["by_topic"]}["LLMs"] == 55


def test_overview_window_excludes_rows_older_than_days(db_session, api_client):
    a = _article(db_session, "Old news")
    today = _utc_today()
    _views(db_session, a, today, 3)
    _views(db_session, a, today - timedelta(days=45), 999)
    db_session.commit()

    body = api_client.get("/admin/analytics/overview?days=30", headers=_ADMIN_HDR).json()
    assert sum(d["views"] for d in body["daily_totals"]) == 3
    assert body["trending"][0]["window_views"] == 3


def test_overview_all_time_top_reads_article_metrics(db_session, api_client):
    from models.article_metrics import ArticleMetrics
    a = _article(db_session, "Evergreen")
    db_session.add(ArticleMetrics(article_id=a.id, view_count=1234))
    db_session.commit()

    body = api_client.get("/admin/analytics/overview", headers=_ADMIN_HDR).json()
    top = {row["title"]: row["total_views"] for row in body["all_time_top"]}
    assert top.get("Evergreen") == 1234


# ---------------------------------------------------------------------------
# flush_view_counts() -> article_view_daily
# ---------------------------------------------------------------------------

def _redis_client():
    return aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


@pytest_asyncio.fixture
async def redis_client():
    r = _redis_client()
    yield r
    await r.aclose()


@pytest.mark.asyncio
async def test_flush_accumulates_into_todays_daily_bucket(db_session, api_client, redis_client):
    from models.article_metrics import ArticleMetrics
    from models.article_view_daily import ArticleViewDaily

    a = _article(db_session, "Flush target")
    db_session.add(ArticleMetrics(article_id=a.id, view_count=0))
    db_session.commit()

    await redis_client.delete(f"view:{a.id}")
    await redis_client.set(f"view:{a.id}", 3)
    assert api_client.post("/admin/articles/flush-view-counts", headers=_ADMIN_HDR).status_code == 200

    await redis_client.set(f"view:{a.id}", 4)  # a second flush the same day
    assert api_client.post("/admin/articles/flush-view-counts", headers=_ADMIN_HDR).status_code == 200

    db_session.expire_all()
    rows = (
        db_session.query(ArticleViewDaily)
        .filter_by(article_id=a.id, day=_utc_today())
        .all()
    )
    assert len(rows) == 1  # one row per (article, day)
    assert rows[0].views == 7  # 3 + 4 accumulated

    await redis_client.delete(f"view:{a.id}")
