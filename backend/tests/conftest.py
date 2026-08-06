import os
import uuid
import time
from unittest.mock import MagicMock

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
