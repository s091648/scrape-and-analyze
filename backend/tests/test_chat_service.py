import pytest
from unittest.mock import AsyncMock, patch

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
    remaining = await service.check_rate_limit(identity)
    assert remaining == -1
    mock_redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_user_rate_limit_increments_key(service, mock_redis):
    identity = ChatIdentity(tier="user", user_id="user-abc")
    mock_redis.incr.return_value = 1
    remaining = await service.check_rate_limit(identity)
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
    remaining = await service.check_rate_limit(identity)
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
