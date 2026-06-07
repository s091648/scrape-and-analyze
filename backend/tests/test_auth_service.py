"""
Unit tests for backend/services/auth_service.py.

Existing test_auth.py tests the router layer with mocked services.
These tests call service functions directly with a mock DB session.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(**kwargs):
    u = MagicMock()
    u.id = kwargs.get("id", uuid.uuid4())
    u.username = kwargs.get("username", "testuser")
    u.email = kwargs.get("email", "test@example.com")
    u.name = kwargs.get("name", "Test User")
    u.role = kwargs.get("role", "user")
    u.is_allowed = kwargs.get("is_allowed", True)
    u.google_id = kwargs.get("google_id", None)
    u.hashed_password = kwargs.get("hashed_password", "$2b$12$placeholder")
    u.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    u.updated_at = kwargs.get("updated_at", None)
    return u


def _mock_db(return_value=None):
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = return_value
    q.all.return_value = [return_value] if return_value else []
    return db


# ---------------------------------------------------------------------------
# get_user_by_username
# ---------------------------------------------------------------------------

def test_get_user_by_username_found():
    from backend.services.auth_service import get_user_by_username

    user = _mock_user(username="alice")
    db = _mock_db(return_value=user)

    with patch("models.auth.User") as MockUser:
        MockUser.username = MagicMock()
        result = get_user_by_username(db, "alice")

    assert result is user
    db.query.assert_called_once()


def test_get_user_by_username_not_found():
    from backend.services.auth_service import get_user_by_username

    db = _mock_db(return_value=None)
    with patch("models.auth.User"):
        result = get_user_by_username(db, "nobody")
    assert result is None


# ---------------------------------------------------------------------------
# get_user_by_email
# ---------------------------------------------------------------------------

def test_get_user_by_email_found():
    from backend.services.auth_service import get_user_by_email

    user = _mock_user(email="a@b.com")
    db = _mock_db(return_value=user)

    with patch("models.auth.User") as MockUser:
        MockUser.email = MagicMock()
        result = get_user_by_email(db, "a@b.com")
    assert result is user


def test_get_user_by_email_not_found():
    from backend.services.auth_service import get_user_by_email

    db = _mock_db(return_value=None)
    with patch("models.auth.User"):
        result = get_user_by_email(db, "missing@b.com")
    assert result is None


# ---------------------------------------------------------------------------
# get_user_by_google_id
# ---------------------------------------------------------------------------

def test_get_user_by_google_id_found():
    from backend.services.auth_service import get_user_by_google_id

    user = _mock_user(google_id="goog-123")
    db = _mock_db(return_value=user)

    with patch("models.auth.User") as MockUser:
        MockUser.google_id = MagicMock()
        result = get_user_by_google_id(db, "goog-123")
    assert result is user


def test_get_user_by_google_id_not_found():
    from backend.services.auth_service import get_user_by_google_id

    db = _mock_db(return_value=None)
    with patch("models.auth.User"):
        result = get_user_by_google_id(db, "unknown-goog")
    assert result is None


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------

def test_get_user_by_id_found():
    from backend.services.auth_service import get_user_by_id

    uid = uuid.uuid4()
    user = _mock_user(id=uid)
    db = _mock_db(return_value=user)

    with patch("models.auth.User") as MockUser:
        MockUser.id = MagicMock()
        result = get_user_by_id(db, uid)
    assert result is user


def test_get_user_by_id_not_found():
    from backend.services.auth_service import get_user_by_id

    db = _mock_db(return_value=None)
    with patch("models.auth.User"):
        result = get_user_by_id(db, uuid.uuid4())
    assert result is None


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------

def test_list_users_returns_ordered_list():
    from backend.services.auth_service import list_users

    user_a = _mock_user(username="alice")
    user_b = _mock_user(username="bob")
    db = MagicMock()
    q = db.query.return_value
    q.order_by.return_value = q
    q.all.return_value = [user_a, user_b]

    with patch("models.auth.User") as MockUser:
        MockUser.created_at = MagicMock()
        result = list_users(db)

    assert len(result) == 2
    assert result[0] is user_a


def test_list_users_empty():
    from backend.services.auth_service import list_users

    db = MagicMock()
    q = db.query.return_value
    q.order_by.return_value = q
    q.all.return_value = []

    with patch("models.auth.User"):
        result = list_users(db)
    assert result == []


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

def test_create_user_adds_and_returns_user():
    from backend.services.auth_service import create_user

    uid = uuid.uuid4()
    db = MagicMock()

    created = _mock_user(id=uid, email="new@test.com")
    db.refresh.side_effect = lambda u: None

    with patch("models.auth.User") as MockUser:
        MockUser.return_value = created
        result = create_user(db, id=uid, email="new@test.com", name="New", role="user")

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------

def test_update_user_applies_fields():
    from backend.services.auth_service import update_user
    from backend.schemas.user import AdminUpdateUserRequest

    user = _mock_user()
    db = MagicMock()
    db.refresh.side_effect = lambda u: None

    data = AdminUpdateUserRequest(role="admin")
    result = update_user(db, user, data)

    assert user.role == "admin"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(user)


def test_update_user_sets_updated_at():
    from backend.services.auth_service import update_user
    from backend.schemas.user import AdminUpdateUserRequest

    user = _mock_user()
    user.updated_at = None
    db = MagicMock()
    db.refresh.side_effect = lambda u: None

    update_user(db, user, AdminUpdateUserRequest(role="user"))

    assert user.updated_at is not None


def test_update_user_excludes_unset_fields():
    from backend.services.auth_service import update_user
    from backend.schemas.user import AdminUpdateUserRequest

    user = _mock_user(role="user", name="Original")
    db = MagicMock()
    db.refresh.side_effect = lambda u: None

    # Only update role, not name
    update_user(db, user, AdminUpdateUserRequest(role="admin"))

    assert user.role == "admin"
    assert user.name == "Original"


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------

def test_delete_user_calls_delete_and_commit():
    from backend.services.auth_service import delete_user

    user = _mock_user()
    db = MagicMock()

    delete_user(db, user)

    db.delete.assert_called_once_with(user)
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# update_google_id
# ---------------------------------------------------------------------------

def test_update_google_id_sets_google_id():
    from backend.services.auth_service import update_google_id

    user = _mock_user(google_id=None)
    db = MagicMock()

    update_google_id(db, user, "new-google-sub")

    assert user.google_id == "new-google-sub"
    db.commit.assert_called_once()


def test_update_google_id_sets_updated_at():
    from backend.services.auth_service import update_google_id

    user = _mock_user()
    user.updated_at = None
    db = MagicMock()

    update_google_id(db, user, "sub-xyz")

    assert user.updated_at is not None


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------

def test_hash_password_returns_bcrypt_hash():
    from backend.services.auth_service import hash_password

    hashed = hash_password("my-secret-password")
    assert hashed.startswith("$2b$")


def test_hash_password_is_not_plaintext():
    from backend.services.auth_service import hash_password

    hashed = hash_password("plaintext")
    assert hashed != "plaintext"


def test_hash_password_different_hashes_for_same_password():
    from backend.services.auth_service import hash_password

    h1 = hash_password("password")
    h2 = hash_password("password")
    assert h1 != h2  # bcrypt salt makes hashes unique


def test_verify_password_correct_returns_true():
    from backend.services.auth_service import hash_password, verify_password

    hashed = hash_password("correct-pass")
    assert verify_password("correct-pass", hashed) is True


def test_verify_password_wrong_returns_false():
    from backend.services.auth_service import hash_password, verify_password

    hashed = hash_password("correct-pass")
    assert verify_password("wrong-pass", hashed) is False


def test_verify_password_empty_string():
    from backend.services.auth_service import hash_password, verify_password

    hashed = hash_password("non-empty")
    assert verify_password("", hashed) is False
