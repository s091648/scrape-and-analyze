import os
import uuid
import time
from unittest.mock import MagicMock

# Set a consistent test secret for all JWT-related tests
os.environ["NEXTAUTH_SECRET"] = "test-secret"

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
