"""Integration tests for view-count tracking (spec 014):

  POST /articles/{id}/view              — Redis incr with per-IP dedup
  POST /admin/articles/flush-view-counts — flush Redis counters into article_metrics

Requires a real Redis instance (REDIS_URL, defaults to redis://redis:6379/0).
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from backend.tests.integration.conftest import admin_token

pytestmark = pytest.mark.integration
_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}


def _redis_client():
    return aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


@pytest_asyncio.fixture
async def redis_client():
    r = _redis_client()
    yield r
    await r.aclose()


def _article(db_session, title="View count article"):
    from models.article import Article
    article = Article(
        id=uuid.uuid4(),
        url=f"https://example.com/{uuid.uuid4().hex}",
        url_hash=uuid.uuid4().hex,
        source="techcrunch",
        title=title,
        content="body",
        correlation_id=uuid.uuid4(),
        scraped_at=datetime.now(timezone.utc),
    )
    db_session.add(article)
    db_session.flush()
    return article


async def _cleanup_view_keys(r, article_id):
    await r.delete(f"view:{article_id}")


# ---------------------------------------------------------------------------
# POST /articles/{id}/view
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_view_increments_redis_counter(db_session, api_client, redis_client):
    article = _article(db_session)
    await _cleanup_view_keys(redis_client, article.id)

    r = api_client.post(f"/articles/{article.id}/view")
    assert r.status_code == 204

    count = await redis_client.get(f"view:{article.id}")
    assert int(count) == 1

    await _cleanup_view_keys(redis_client, article.id)


@pytest.mark.asyncio
async def test_record_view_dedups_same_ip_within_24h(db_session, api_client, redis_client):
    article = _article(db_session)
    await _cleanup_view_keys(redis_client, article.id)

    r1 = api_client.post(f"/articles/{article.id}/view")
    r2 = api_client.post(f"/articles/{article.id}/view")
    assert r1.status_code == 204
    assert r2.status_code == 204

    count = await redis_client.get(f"view:{article.id}")
    assert int(count) == 1  # second call from the same IP is deduped

    dedup_keys = [k async for k in redis_client.scan_iter(match=f"viewed:*:{article.id}")]
    await _cleanup_view_keys(redis_client, article.id)
    for k in dedup_keys:
        await redis_client.delete(k)


# ---------------------------------------------------------------------------
# POST /admin/articles/flush-view-counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flush_view_counts_moves_redis_counts_into_article_metrics(db_session, api_client, redis_client):
    from models.article_metrics import ArticleMetrics

    article = _article(db_session)
    db_session.add(ArticleMetrics(article_id=article.id, view_count=0))
    db_session.flush()
    db_session.commit()

    await _cleanup_view_keys(redis_client, article.id)
    await redis_client.set(f"view:{article.id}", 5)

    r = api_client.post("/admin/articles/flush-view-counts", headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["flushed"] >= 1

    db_session.expire_all()
    metrics = db_session.query(ArticleMetrics).filter_by(article_id=article.id).first()
    assert metrics.view_count == 5

    # The Redis key should have been consumed (getdel) during flush
    assert await redis_client.get(f"view:{article.id}") is None


@pytest.mark.asyncio
async def test_flush_view_counts_skips_zero_and_negative_counts(db_session, api_client, redis_client):
    from models.article_metrics import ArticleMetrics

    article = _article(db_session)
    db_session.add(ArticleMetrics(article_id=article.id, view_count=10))
    db_session.flush()
    db_session.commit()

    await _cleanup_view_keys(redis_client, article.id)
    await redis_client.set(f"view:{article.id}", 0)

    r = api_client.post("/admin/articles/flush-view-counts", headers=_ADMIN_HDR)
    assert r.status_code == 200

    db_session.expire_all()
    metrics = db_session.query(ArticleMetrics).filter_by(article_id=article.id).first()
    assert metrics.view_count == 10  # unchanged — zero counts are not flushed

    await _cleanup_view_keys(redis_client, article.id)
