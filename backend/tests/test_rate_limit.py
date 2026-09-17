"""Unit tests for backend/rate_limit/ — the policy registry + Redis fixed-window
limiter core, exercised directly (not through a router), mirroring
test_chat_router.py's `_make_redis` mocking pattern (no real Redis)."""
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def make_counting_redis(ttl=30):
    """A minimal fake honoring real Redis INCR semantics: per-key counters, keyed by
    the exact key passed to the atomic INCR+EXPIRE Lua script (limiter.py) — good
    enough to prove two different keys (different origins/identities/policies)
    never share a counter."""
    redis = AsyncMock()
    counts: dict[str, int] = {}

    async def eval_incr_and_expire(script, numkeys, key, window_seconds):
        counts[key] = counts.get(key, 0) + 1
        return counts[key]

    redis.eval = AsyncMock(side_effect=eval_incr_and_expire)
    redis.ttl = AsyncMock(return_value=ttl)
    redis.aclose = AsyncMock()
    redis._counts = counts
    return redis


def make_scoped_request(client_host="1.2.3.4", forwarded_for=None):
    """Minimal ASGI scope — just enough for get_client_origin() to resolve an origin."""
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    scope = {"type": "http", "headers": headers, "client": (client_host, 12345)}
    return Request(scope)


# ---------------------------------------------------------------------------
# guest_token policy (US1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guest_token_policy_allows_within_limit_refuses_excess_leaves_other_origin_unaffected():
    from backend.rate_limit.limiter import guest_token_limit
    from backend.config import RATE_LIMIT_GUEST_TOKEN_MAX
    from shared.domain.exceptions import RateLimitExceededError

    mock_redis = make_counting_redis()
    request_a = make_scoped_request(client_host="1.2.3.4")
    request_b = make_scoped_request(client_host="9.9.9.9")

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        for _ in range(RATE_LIMIT_GUEST_TOKEN_MAX):
            await guest_token_limit(request_a)  # within limit — must not raise

        with pytest.raises(RateLimitExceededError):
            await guest_token_limit(request_a)  # exceeds — refused

        await guest_token_limit(request_b)  # different origin — unaffected, must not raise


@pytest.mark.asyncio
async def test_guest_token_refusal_carries_retry_after_seconds():
    from backend.rate_limit.limiter import guest_token_limit
    from backend.config import RATE_LIMIT_GUEST_TOKEN_MAX
    from shared.domain.exceptions import RateLimitExceededError

    mock_redis = make_counting_redis(ttl=17)
    request = make_scoped_request(client_host="1.2.3.4")

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        for _ in range(RATE_LIMIT_GUEST_TOKEN_MAX):
            await guest_token_limit(request)
        with pytest.raises(RateLimitExceededError) as exc_info:
            await guest_token_limit(request)

    assert exc_info.value.retry_after_seconds == 17


# ---------------------------------------------------------------------------
# auth_attempt policy (US2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_attempt_policy_allows_within_limit_refuses_excess_from_same_origin():
    from backend.rate_limit.limiter import auth_attempt_limit
    from backend.config import RATE_LIMIT_AUTH_ATTEMPT_MAX
    from shared.domain.exceptions import RateLimitExceededError

    mock_redis = make_counting_redis()
    request = make_scoped_request(client_host="5.5.5.5")

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        for _ in range(RATE_LIMIT_AUTH_ATTEMPT_MAX):
            await auth_attempt_limit(request)  # within limit — must not raise

        with pytest.raises(RateLimitExceededError):
            await auth_attempt_limit(request)


@pytest.mark.asyncio
async def test_auth_attempt_and_guest_token_policies_never_share_a_counter():
    """Same origin hitting both policies must not let one policy's count leak into
    the other's — they're keyed by policy name (ratelimit:{name}:{origin})."""
    from backend.rate_limit.limiter import auth_attempt_limit, guest_token_limit
    from backend.config import RATE_LIMIT_GUEST_TOKEN_MAX

    mock_redis = make_counting_redis()
    request = make_scoped_request(client_host="5.5.5.5")

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        for _ in range(RATE_LIMIT_GUEST_TOKEN_MAX):
            await guest_token_limit(request)  # exhaust guest_token for this origin
        await auth_attempt_limit(request)  # auth_attempt's own counter is untouched — must not raise


# ---------------------------------------------------------------------------
# chat_burst policy (US3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_burst_policy_allows_within_limit_and_refuses_excess():
    from backend.rate_limit.limiter import chat_burst_limit
    from backend.config import RATE_LIMIT_CHAT_BURST_MAX
    from shared.domain.exceptions import RateLimitExceededError

    mock_redis = make_counting_redis()
    guest_payload = {"tier": "guest", "guest_id": "known-guest-id"}

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        for _ in range(RATE_LIMIT_CHAT_BURST_MAX):
            await chat_burst_limit(guest_payload)  # within limit — must not raise

        with pytest.raises(RateLimitExceededError):
            await chat_burst_limit(guest_payload)


@pytest.mark.asyncio
async def test_chat_burst_key_is_namespaced_separately_from_daily_quota_key():
    from backend.rate_limit.limiter import chat_burst_limit

    mock_redis = make_counting_redis()
    guest_payload = {"tier": "guest", "guest_id": "known-guest-id"}

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        await chat_burst_limit(guest_payload)

    used_key = mock_redis.eval.call_args_list[0][0][2]
    assert used_key == "ratelimit:chat_burst:guest:known-guest-id"
    # chat_service.py's existing daily quota uses a "rate:guest:{id}:{date}" shape —
    # confirm the two mechanisms can never collide even though they share a Redis DB.
    assert not used_key.startswith("rate:guest:")


@pytest.mark.asyncio
async def test_increment_and_expiry_use_one_atomic_eval_call():
    """CodeRabbit review (026-rate-limit-codegen PR #127): INCR and EXPIRE must
    happen in a single atomic Redis script, not two separate round-trips —
    otherwise a cancellation between them leaves the key with no TTL and the
    origin/identity stays rate-limited forever once it hits the max."""
    from backend.rate_limit.limiter import guest_token_limit, _INCR_AND_EXPIRE_SCRIPT
    from backend.config import RATE_LIMIT_GUEST_TOKEN_WINDOW_SECONDS

    mock_redis = make_counting_redis()
    request = make_scoped_request(client_host="7.7.7.7")

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        await guest_token_limit(request)

    mock_redis.eval.assert_called_once_with(
        _INCR_AND_EXPIRE_SCRIPT, 1, "ratelimit:guest_token:7.7.7.7", RATE_LIMIT_GUEST_TOKEN_WINDOW_SECONDS
    )


@pytest.mark.asyncio
async def test_chat_burst_admin_bypasses_like_the_existing_daily_quota_does():
    from backend.rate_limit.limiter import chat_burst_limit

    mock_redis = make_counting_redis()
    admin_payload = {"role": "admin", "sub": "admin-1"}

    with patch("backend.rate_limit.limiter._make_redis", return_value=mock_redis):
        await chat_burst_limit(admin_payload)

    mock_redis.eval.assert_not_called()


# ---------------------------------------------------------------------------
# Polish: Redis-unavailable fail-open behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_error_during_check_fails_open():
    from backend.rate_limit.limiter import guest_token_limit

    failing_redis = AsyncMock()
    failing_redis.eval = AsyncMock(side_effect=ConnectionError("redis unreachable"))
    failing_redis.aclose = AsyncMock()

    request = make_scoped_request(client_host="1.2.3.4")

    with patch("backend.rate_limit.limiter._make_redis", return_value=failing_redis):
        await guest_token_limit(request)  # must not raise — the request is allowed through
