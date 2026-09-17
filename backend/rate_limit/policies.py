from dataclasses import dataclass

from backend.config import (
    RATE_LIMIT_GUEST_TOKEN_MAX,
    RATE_LIMIT_GUEST_TOKEN_WINDOW_SECONDS,
    RATE_LIMIT_AUTH_ATTEMPT_MAX,
    RATE_LIMIT_AUTH_ATTEMPT_WINDOW_SECONDS,
    RATE_LIMIT_CHAT_BURST_MAX,
    RATE_LIMIT_CHAT_BURST_WINDOW_SECONDS,
    RATE_LIMIT_SEARCH_MAX,
    RATE_LIMIT_SEARCH_WINDOW_SECONDS,
)


@dataclass(frozen=True)
class RateLimitPolicy:
    """A named rule protecting one capability (data-model.md). `name` also doubles as
    the Redis key prefix (`ratelimit:{name}:{...}`, limiter.py)."""

    name: str
    max_requests: int
    window_seconds: int


GUEST_TOKEN = RateLimitPolicy("guest_token", RATE_LIMIT_GUEST_TOKEN_MAX, RATE_LIMIT_GUEST_TOKEN_WINDOW_SECONDS)
AUTH_ATTEMPT = RateLimitPolicy("auth_attempt", RATE_LIMIT_AUTH_ATTEMPT_MAX, RATE_LIMIT_AUTH_ATTEMPT_WINDOW_SECONDS)
CHAT_BURST = RateLimitPolicy("chat_burst", RATE_LIMIT_CHAT_BURST_MAX, RATE_LIMIT_CHAT_BURST_WINDOW_SECONDS)
SEARCH = RateLimitPolicy("search", RATE_LIMIT_SEARCH_MAX, RATE_LIMIT_SEARCH_WINDOW_SECONDS)
