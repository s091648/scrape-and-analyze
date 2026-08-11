import os
import uuid
import time
from unittest.mock import MagicMock

import pytest

# Set a consistent test secret for all JWT-related tests
os.environ["NEXTAUTH_SECRET"] = "test-secret"
# Provide a syntactically valid dummy URL so SQLAlchemy doesn't blow up at import
# time in unit tests that don't have a real database available.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/testdb")

# backend/main.py unconditionally calls sentry_sdk.init() and configure_logging()/
# setup_tracing() at import time whenever these are set. A dev .env (loaded into the
# test container via docker-compose's env_file) has real Grafana Cloud / Sentry
# credentials, which would otherwise make every test that hits the app through
# TestClient — via RequestLoggingMiddleware's per-request `logger.info("request", ...)`
# — perform a real synchronous HTTP POST to Grafana Loki (logging_loki.LokiHandler.emit
# is synchronous, not queued), plus real Sentry/OTel client setup. That's on the order of
# 1-1.5s of real network latency per test across the whole suite. Force these off for
# the test session regardless of what's in the process env.
os.environ["SENTRY_DSN"] = ""
os.environ["GRAFANA_OTLP_USER"] = ""
os.environ["GRAFANA_OTLP_ENDPOINT"] = ""
os.environ["GRAFANA_LOKI_URL"] = ""
os.environ["GRAFANA_LOKI_USER"] = ""

SECRET = os.environ["NEXTAUTH_SECRET"]


# ── Auth helpers ─────────────────────────────────────────────────────────────


def make_admin_token():
    """Create a JWT token with admin role."""
    from jose import jwt
    payload = {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def make_user_token():
    """Create a JWT token with regular user role."""
    from jose import jwt
    payload = {"sub": "user", "role": "user", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def make_guest_token(guest_id="test-guest-id"):
    """Create a guest access token (018-public-api-auth) — every endpoint that used
    to require no auth at all now requires at least a guest token."""
    from backend.services.auth_service import create_guest_access_token
    return create_guest_access_token(guest_id)


# ── ORM mock factories ──────────────────────────────────────────────────────


def make_mock_tag_group(**kwargs):
    """Create a mock TagGroupDefinition ORM instance."""
    defaults = dict(
        id=uuid.uuid4(),
        name="test_group",
        display_name="Test Group",
        description=None,
        color_hex=None,
        topic_id=uuid.uuid4(),
        embedding=None,
        sort_order=0,
    )
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def make_mock_tag(**kwargs):
    """Create a mock Tag ORM instance."""
    defaults = dict(
        id=uuid.uuid4(),
        name="TestTag",
        tag_group_id=uuid.uuid4(),
        tag_group_name="test_group",
        embedding=None,
    )
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ── Cache isolation ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_cache_by_default(request):
    """020-redis-caching-layer: routers depend on a real Redis-backed CacheGateway
    (backend/cache.py's module-level singleton). Real cache-aside behavior is covered
    by backend/tests/integration/ (test_articles.py, test_graph.py, test_tags.py,
    test_weekly_reports.py) — unit tests that don't explicitly override
    get_cache_gateway would otherwise all share one real Redis key namespace for the
    whole session, so whichever test hits a given (namespace, params) key first "wins"
    and every later test with the same params gets that first test's stale mocked
    response instead of its own. Bypass caching by default; tests that want to assert
    real cache-hit behavior already override this themselves with an in-memory fake
    (see _InMemoryFakeCacheGateway in test_graph.py) or, for integration tests (see
    below), use the real gateway untouched.

    For @pytest.mark.integration tests: this fixture is defined here (rather than a
    unit-only conftest) because backend/tests/ has no separate unit-test subdirectory,
    but pytest still applies it to backend/tests/integration/ by directory inheritance
    — integration tests need the real RedisCacheGateway singleton to actually exercise
    cache-aside behavior against the redis service container, not this bypass fake.
    But the real gateway is a session-wide singleton against one real Redis instance,
    so two integration tests calling the same endpoint with the same (namespace,
    params) — e.g. GET /articles with no filters — would otherwise collide: whichever
    test populates that key first "wins" and every later test with identical default
    params reads that first test's stale response instead of its own. Bump every known
    namespace before each integration test so it always starts from a clean version
    (still exercising real cache-aside — hits/misses *within* a single test still work
    exactly as they would in production — just guaranteed isolated *across* tests)."""
    if request.node.get_closest_marker("integration"):
        from backend.cache import cache_gateway
        for namespace in ("articles", "graph", "tag_groups", "weekly_reports", "topics"):
            cache_gateway.bump_version(namespace)
        yield
        return

    from backend.main import app
    from backend.cache import get_cache_gateway

    from shared.cache import CacheResult

    class _NoCacheGateway:
        def get_or_set(self, namespace, params, ttl_seconds, loader, lang="en"):
            return CacheResult(value=loader(), status="BYPASS")

        def bump_version(self, namespace):
            return 0

    app.dependency_overrides[get_cache_gateway] = lambda: _NoCacheGateway()
    yield
    app.dependency_overrides.pop(get_cache_gateway, None)


def make_mock_suggestion(**kwargs):
    """Create a mock TagNormalizationSuggestion ORM instance."""
    defaults = dict(
        id=uuid.uuid4(),
        new_tag_id=uuid.uuid4(),
        existing_tag_id=uuid.uuid4(),
        similarity_score=0.92,
        status="pending",
        article_id=None,
        resolved_at=None,
        resolved_by=None,
    )
    defaults.update(kwargs)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock
