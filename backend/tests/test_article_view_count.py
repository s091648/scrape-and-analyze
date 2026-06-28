import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_redis_mock(already_viewed=False):
    r = AsyncMock()
    r.get.return_value = b"1" if already_viewed else None
    r.incr = AsyncMock()
    r.expire = AsyncMock()
    r.aclose = AsyncMock()
    return r


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_view_endpoint_returns_204(client):
    article_id = uuid.uuid4()
    mock_redis = _make_redis_mock()
    with patch("backend.routers.articles._get_redis", return_value=mock_redis):
        r = client.post(f"/articles/{article_id}/view")
    assert r.status_code == 204


def test_view_increments_redis_key_on_first_view(client):
    article_id = uuid.uuid4()
    mock_redis = _make_redis_mock(already_viewed=False)
    with patch("backend.routers.articles._get_redis", return_value=mock_redis):
        client.post(f"/articles/{article_id}/view")
    mock_redis.incr.assert_awaited_once_with(f"view:{article_id}")


def test_view_sets_dedup_ttl_on_first_view(client):
    article_id = uuid.uuid4()
    mock_redis = _make_redis_mock(already_viewed=False)
    with patch("backend.routers.articles._get_redis", return_value=mock_redis):
        client.post(f"/articles/{article_id}/view")
    mock_redis.expire.assert_awaited_once()
    args = mock_redis.expire.call_args[0]
    assert args[1] == 86400


def test_view_does_not_increment_on_second_view_same_ip(client):
    article_id = uuid.uuid4()
    mock_redis = _make_redis_mock(already_viewed=True)
    with patch("backend.routers.articles._get_redis", return_value=mock_redis):
        client.post(f"/articles/{article_id}/view")
    mock_redis.incr.assert_not_awaited()


def test_view_still_returns_204_on_duplicate(client):
    article_id = uuid.uuid4()
    mock_redis = _make_redis_mock(already_viewed=True)
    with patch("backend.routers.articles._get_redis", return_value=mock_redis):
        r = client.post(f"/articles/{article_id}/view")
    assert r.status_code == 204
