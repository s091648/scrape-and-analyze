import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.chat_service import (
    DAILY_LIMIT_GUEST,
    DAILY_LIMIT_USER,
    ChatIdentity,
    ChatService,
    RateLimitExceeded,
)


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    return redis


@pytest.fixture
def service(mock_redis):
    return ChatService(redis_client=mock_redis)


@pytest.mark.asyncio
async def test_admin_bypasses_rate_limit(service, mock_redis):
    identity = ChatIdentity(tier="admin", user_id="admin-1")
    remaining, limit = await service.check_rate_limit(identity)
    assert remaining == -1
    mock_redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_user_rate_limit_increments_key(service, mock_redis):
    identity = ChatIdentity(tier="user", user_id="user-abc")
    mock_redis.incr.return_value = 1
    remaining, _ = await service.check_rate_limit(identity)
    assert remaining == DAILY_LIMIT_USER - 1
    key_used = mock_redis.incr.call_args[0][0]
    assert "rate:user:user-abc" in key_used


@pytest.mark.asyncio
async def test_user_rate_limit_exceeded(service, mock_redis):
    identity = ChatIdentity(tier="user", user_id="user-abc")
    mock_redis.incr.return_value = DAILY_LIMIT_USER + 1
    with pytest.raises(RateLimitExceeded) as exc_info:
        await service.check_rate_limit(identity)
    assert exc_info.value.limit == DAILY_LIMIT_USER


@pytest.mark.asyncio
async def test_guest_rate_limit_with_cookie(service, mock_redis):
    identity = ChatIdentity(tier="guest", guest_id="cookie-uuid-123")
    mock_redis.incr.return_value = 1
    remaining, _ = await service.check_rate_limit(identity)
    assert remaining == DAILY_LIMIT_GUEST - 1
    key_used = mock_redis.incr.call_args[0][0]
    assert "rate:guest:cookie-uuid-123" in key_used


@pytest.mark.asyncio
async def test_guest_rate_limit_with_ip_fallback(service, mock_redis):
    identity = ChatIdentity(tier="guest", guest_id="ip:abc123def456")
    mock_redis.incr.return_value = 1
    await service.check_rate_limit(identity)
    key_used = mock_redis.incr.call_args[0][0]
    assert "rate:guest:ip:abc123def456" in key_used


@pytest.mark.asyncio
async def test_guest_rate_limit_exceeded(service, mock_redis):
    identity = ChatIdentity(tier="guest", guest_id="cookie-uuid-123")
    mock_redis.incr.return_value = DAILY_LIMIT_GUEST + 1
    with pytest.raises(RateLimitExceeded) as exc_info:
        await service.check_rate_limit(identity)
    assert exc_info.value.limit == DAILY_LIMIT_GUEST


@pytest.mark.asyncio
async def test_first_incr_sets_expiry(service, mock_redis):
    identity = ChatIdentity(tier="user", user_id="user-new")
    mock_redis.incr.return_value = 1
    await service.check_rate_limit(identity)
    mock_redis.expire.assert_called_once()
    _, expire_seconds = mock_redis.expire.call_args[0]
    assert expire_seconds == 86400


@pytest.mark.asyncio
async def test_subsequent_incr_does_not_set_expiry(service, mock_redis):
    identity = ChatIdentity(tier="user", user_id="user-returning")
    mock_redis.incr.return_value = 5
    await service.check_rate_limit(identity)
    mock_redis.expire.assert_not_called()


# ── get_quota ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_quota_admin_returns_unlimited(service, mock_redis):
    identity = ChatIdentity(tier="admin", user_id="admin-1")
    remaining, limit = await service.get_quota(identity)
    assert remaining == -1
    assert limit == -1
    mock_redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_quota_user_with_no_usage(service, mock_redis):
    mock_redis.get = AsyncMock(return_value=None)
    identity = ChatIdentity(tier="user", user_id="user-abc")
    remaining, limit = await service.get_quota(identity)
    assert limit == DAILY_LIMIT_USER
    assert remaining == DAILY_LIMIT_USER


@pytest.mark.asyncio
async def test_get_quota_user_with_some_usage(service, mock_redis):
    mock_redis.get = AsyncMock(return_value=b"10")
    identity = ChatIdentity(tier="user", user_id="user-abc")
    remaining, limit = await service.get_quota(identity)
    assert limit == DAILY_LIMIT_USER
    assert remaining == DAILY_LIMIT_USER - 10


@pytest.mark.asyncio
async def test_get_quota_user_at_limit_clamps_to_zero(service, mock_redis):
    mock_redis.get = AsyncMock(return_value=str(DAILY_LIMIT_USER + 5).encode())
    identity = ChatIdentity(tier="user", user_id="user-abc")
    remaining, limit = await service.get_quota(identity)
    assert remaining == 0


@pytest.mark.asyncio
async def test_get_quota_guest_with_no_usage(service, mock_redis):
    mock_redis.get = AsyncMock(return_value=None)
    identity = ChatIdentity(tier="guest", guest_id="cookie-abc")
    remaining, limit = await service.get_quota(identity)
    assert limit == DAILY_LIMIT_GUEST
    assert remaining == DAILY_LIMIT_GUEST


@pytest.mark.asyncio
async def test_get_quota_reads_correct_key(service, mock_redis):
    mock_redis.get = AsyncMock(return_value=b"1")
    identity = ChatIdentity(tier="guest", guest_id="ip:deadbeef")
    await service.get_quota(identity)
    key_used = mock_redis.get.call_args[0][0]
    assert "rate:guest:ip:deadbeef" in key_used


# ── stream_completions ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_completions_yields_response_bytes():
    service = ChatService(redis_client=None)

    chunks = [b"data: chunk1\n\n", b"data: [DONE]\n\n"]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def _aiter_bytes():
        for c in chunks:
            yield c

    mock_response.aiter_bytes = _aiter_bytes

    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.services.chat_service.httpx.AsyncClient", return_value=mock_client_cm):
        result = []
        async for chunk in service.stream_completions(
            messages=[{"role": "user", "content": "hello"}]
        ):
            result.append(chunk)

    assert result == chunks


@pytest.mark.asyncio
async def test_stream_completions_includes_topic_id_in_body():
    service = ChatService(redis_client=None)
    captured_body = {}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def _aiter_bytes():
        return
        yield  # make it an async generator

    mock_response.aiter_bytes = _aiter_bytes

    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    def _stream(method, url, json, headers):
        captured_body.update(json)
        return mock_stream_cm

    mock_client = MagicMock()
    mock_client.stream = _stream

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.services.chat_service.httpx.AsyncClient", return_value=mock_client_cm):
        async for _ in service.stream_completions(
            messages=[{"role": "user", "content": "hi"}],
            topic_id="topic-xyz",
        ):
            pass

    assert captured_body.get("topic_id") == "topic-xyz"
    assert captured_body.get("stream") is True


@pytest.mark.asyncio
async def test_stream_completions_omits_topic_id_when_none():
    service = ChatService(redis_client=None)
    captured_body = {}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def _aiter_bytes():
        return
        yield

    mock_response.aiter_bytes = _aiter_bytes

    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    def _stream(method, url, json, headers):
        captured_body.update(json)
        return mock_stream_cm

    mock_client = MagicMock()
    mock_client.stream = _stream

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.services.chat_service.httpx.AsyncClient", return_value=mock_client_cm):
        async for _ in service.stream_completions(
            messages=[{"role": "user", "content": "hi"}],
            topic_id=None,
        ):
            pass

    assert "topic_id" not in captured_body
