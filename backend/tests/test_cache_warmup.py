"""Unit tests for backend/cache_warmup.py — the ASGI-in-process cache warm-up triggered by the
Redis Pub/Sub signal, replacing the old HTTP self-call CacheWarmupHandler used to make
(020-redis-caching-layer follow-up). Calls backend's own FastAPI app via httpx's ASGITransport,
so these tests fake AsyncClient itself rather than any router/service function — the whole point
of this design is that warm-up never encodes endpoint-specific knowledge of its own."""
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


class _FakeResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json_data = json_data if json_data is not None else {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """Records every .get() call's (path, params); /topics returns a configurable topic list."""

    def __init__(self, topics=None, fail_paths=None):
        self.calls = []
        self._topics = topics if topics is not None else []
        self._fail_paths = fail_paths or set()

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, path, params=None, headers=None):
        self.calls.append((path, params or {}))
        if path in self._fail_paths:
            return _FakeResponse(status_code=500)
        if path == "/topics":
            return _FakeResponse(json_data=[{"id": t} for t in self._topics])
        return _FakeResponse(json_data={})


@pytest.mark.asyncio
async def test_warm_default_reads_covers_topic_less_and_every_active_topic_in_both_languages():
    from backend.cache_warmup import warm_default_reads

    fake_client = _FakeAsyncClient(topics=["topic-1"])
    with patch("backend.cache_warmup.AsyncClient", fake_client):
        await warm_default_reads(reason="scraper_pipeline")

    paths_warmed = {c[0] for c in fake_client.calls}
    assert paths_warmed == {"/topics", "/articles", "/analyses/graph", "/tag-groups", "/weekly-reports/latest"}

    articles_calls = {
        (c[1].get("topic_id"), c[1]["lang"]) for c in fake_client.calls if c[0] == "/articles"
    }
    assert articles_calls == {(None, "en"), (None, "zh-TW"), ("topic-1", "en"), ("topic-1", "zh-TW")}

    # weekly-reports/latest has no topic-less variant (topic_id is required)
    report_calls = {(c[1].get("topic_id"), c[1]["lang"]) for c in fake_client.calls if c[0] == "/weekly-reports/latest"}
    assert report_calls == {("topic-1", "en"), ("topic-1", "zh-TW")}

    # tag-groups doesn't vary by language — one call per topic (incl. topic-less), not two
    tag_group_calls = [c for c in fake_client.calls if c[0] == "/tag-groups"]
    assert len(tag_group_calls) == 2


@pytest.mark.asyncio
async def test_warm_default_reads_sends_no_topic_id_param_when_topic_less():
    """Omitting the param entirely (not sending topic_id="None") is what makes this match a
    real browser's default request — the router's own Query(default=None) then resolves it."""
    from backend.cache_warmup import warm_default_reads

    fake_client = _FakeAsyncClient(topics=[])
    with patch("backend.cache_warmup.AsyncClient", fake_client):
        await warm_default_reads(reason="scraper_pipeline")

    articles_call = next(c for c in fake_client.calls if c[0] == "/articles")
    assert "topic_id" not in articles_call[1]


@pytest.mark.asyncio
async def test_sends_guest_bearer_token_on_every_call():
    from backend.cache_warmup import warm_default_reads

    seen_headers = []
    fake_client = _FakeAsyncClient(topics=[])
    original_get = fake_client.get

    async def _get(path, params=None, headers=None):
        seen_headers.append(headers)
        return await original_get(path, params=params, headers=headers)

    fake_client.get = _get

    with patch("backend.cache_warmup.AsyncClient", fake_client):
        await warm_default_reads(reason="scraper_pipeline")

    assert all(h and h["Authorization"].startswith("Bearer ") for h in seen_headers)


@pytest.mark.asyncio
async def test_one_failing_target_does_not_abort_the_rest():
    from backend.cache_warmup import warm_default_reads

    fake_client = _FakeAsyncClient(topics=["topic-1"], fail_paths={"/articles"})
    with patch("backend.cache_warmup.AsyncClient", fake_client):
        await warm_default_reads(reason="scraper_pipeline")  # must not raise

    paths_warmed = {c[0] for c in fake_client.calls}
    assert "/analyses/graph" in paths_warmed
    assert "/tag-groups" in paths_warmed
    assert "/weekly-reports/latest" in paths_warmed


@pytest.mark.asyncio
async def test_topic_lookup_failure_skips_warming_entirely_without_raising():
    from backend.cache_warmup import warm_default_reads

    fake_client = _FakeAsyncClient(fail_paths={"/topics"})
    with patch("backend.cache_warmup.AsyncClient", fake_client):
        await warm_default_reads(reason="scraper_pipeline")  # must not raise

    # topic lookup failed -> _active_topic_ids() returns [] -> only the topic-less pass runs
    paths_warmed = {c[0] for c in fake_client.calls}
    assert paths_warmed == {"/topics", "/articles", "/analyses/graph", "/tag-groups"}
