"""
Integration tests for /auth endpoints.

backend/tests/test_auth.py mocks the DB session entirely (MagicMock), including
the IntegrityError that backend/routers/auth.py catches to turn a duplicate
email/username into a 409 (bd7d0a5 — detect duplicates via the real constraint
violation, not string matching). These tests exercise that against the real
`auth.users` table instead, plus the rest of the admin user-management and
`/me` surface that only had mocked coverage before.

Note: `auth.User` lives in a fixed schema (`auth`), not one of the DDD-bounded-
context schemas conftest.py's schema_translate_map redirects into the disposable
`backend_test` schema — so these tests hit the real `auth.users` table on
whatever Postgres DATABASE_URL points at for the test run. Isolation still
holds: db_session wraps every test in an outer transaction (savepoint mode)
that's always rolled back, so nothing persists past the test.
"""
import uuid

import pytest

from backend.tests.integration.conftest import admin_token, user_token

pytestmark = pytest.mark.integration

_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}


def _seed_user(db_session, **kwargs):
    from models.auth import User
    from backend.services.auth_service import hash_password

    defaults = dict(
        id=uuid.uuid4(),
        email=f"seed-{uuid.uuid4().hex[:8]}@example.com",
        name="Seed User",
        role="user",
        is_allowed=True,
    )
    if "password" in kwargs:
        kwargs["hashed_password"] = hash_password(kwargs.pop("password"))
    defaults.update(kwargs)
    user = User(**defaults)
    db_session.add(user)
    db_session.flush()
    return user


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

def test_register_credentials_persists_real_user(api_client, db_session):
    r = api_client.app_client.post("/auth/register", json={
        "username": f"newuser-{uuid.uuid4().hex[:8]}",
        "password": "hunter2hunter2",
        "email": f"new-{uuid.uuid4().hex[:8]}@example.com",
        "name": "New User",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "user"
    assert data["is_allowed"] is True

    from models.auth import User
    row = db_session.query(User).filter(User.id == uuid.UUID(data["id"])).first()
    assert row is not None
    assert row.hashed_password is not None
    assert row.hashed_password != "hunter2hunter2"  # actually hashed, not stored raw


def test_register_google_persists_real_user(api_client, db_session):
    r = api_client.app_client.post("/auth/register", json={
        "email": f"google-{uuid.uuid4().hex[:8]}@example.com",
        "name": "Google User",
        "google_id": f"g-{uuid.uuid4().hex[:8]}",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["google_id"] is not None
    assert data["username"] is None


def test_register_duplicate_username_returns_409_via_real_constraint(api_client, db_session):
    existing = _seed_user(db_session, username="dupe-user", password="whatever123")

    r = api_client.app_client.post("/auth/register", json={
        "username": existing.username,
        "password": "different-password",
        "email": f"other-{uuid.uuid4().hex[:8]}@example.com",
    })
    assert r.status_code == 409


def test_register_duplicate_email_returns_409_via_real_constraint(api_client, db_session):
    existing = _seed_user(db_session, email="taken@example.com")

    r = api_client.app_client.post("/auth/register", json={
        "username": f"someone-{uuid.uuid4().hex[:8]}",
        "password": "different-password",
        "email": existing.email,
    })
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# GET/POST/PATCH/DELETE /auth/users — admin only
# ---------------------------------------------------------------------------

def test_list_users_requires_admin(api_client):
    r = api_client.app_client.get("/auth/users")
    assert r.status_code == 401


def test_list_users_as_admin_returns_seeded_user(api_client, db_session):
    seeded = _seed_user(db_session, email=f"listed-{uuid.uuid4().hex[:8]}@example.com")

    r = api_client.get("/auth/users", headers=_ADMIN_HDR)
    assert r.status_code == 200
    ids = [u["id"] for u in r.json()]
    assert str(seeded.id) in ids


def test_admin_create_user_persists(api_client, db_session):
    email = f"admin-created-{uuid.uuid4().hex[:8]}@example.com"
    r = api_client.post("/auth/users", json={
        "email": email, "name": "Admin Created", "role": "admin",
    }, headers=_ADMIN_HDR)
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "admin"

    from models.auth import User
    row = db_session.query(User).filter(User.email == email).first()
    assert row is not None
    assert row.role == "admin"


def test_admin_create_user_duplicate_email_returns_409(api_client, db_session):
    existing = _seed_user(db_session, email="already-here@example.com")

    r = api_client.post("/auth/users", json={"email": existing.email}, headers=_ADMIN_HDR)
    assert r.status_code == 409


def test_update_user_role_persists(api_client, db_session):
    seeded = _seed_user(db_session, role="user")

    r = api_client.patch(f"/auth/users/{seeded.id}", json={"role": "admin"}, headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"

    db_session.refresh(seeded)
    assert seeded.role == "admin"


def test_update_user_not_found_returns_404(api_client):
    r = api_client.patch(f"/auth/users/{uuid.uuid4()}", json={"role": "admin"}, headers=_ADMIN_HDR)
    assert r.status_code == 404


def test_delete_user_removes_row(api_client, db_session):
    seeded = _seed_user(db_session)
    user_id = seeded.id

    r = api_client.delete(f"/auth/users/{user_id}", headers=_ADMIN_HDR)
    assert r.status_code == 204

    from models.auth import User
    assert db_session.query(User).filter(User.id == user_id).first() is None


def test_delete_user_not_found_returns_404(api_client):
    r = api_client.delete(f"/auth/users/{uuid.uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /auth/me — the caller's own profile
# ---------------------------------------------------------------------------

def test_get_me_requires_auth(api_client):
    r = api_client.app_client.get("/auth/me")
    assert r.status_code == 401


def test_get_me_returns_seeded_profile(api_client, db_session):
    seeded = _seed_user(db_session, name="Self Profile")

    r = api_client.get("/auth/me", headers={"Authorization": f"Bearer {user_token(str(seeded.id))}"})
    assert r.status_code == 200
    assert r.json()["name"] == "Self Profile"


def test_update_me_persists_name(api_client, db_session):
    seeded = _seed_user(db_session, name="Old Name")
    hdr = {"Authorization": f"Bearer {user_token(str(seeded.id))}"}

    r = api_client.patch("/auth/me", json={"name": "New Name"}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"

    db_session.refresh(seeded)
    assert seeded.name == "New Name"


def test_change_password_persists_new_hash(api_client, db_session):
    from backend.services.auth_service import verify_password
    seeded = _seed_user(db_session, username=f"pwuser-{uuid.uuid4().hex[:8]}", password="old-password-123")
    hdr = {"Authorization": f"Bearer {user_token(str(seeded.id))}"}

    r = api_client.post("/auth/me/password", json={
        "current_password": "old-password-123",
        "new_password": "new-password-456",
    }, headers=hdr)
    assert r.status_code == 204

    db_session.refresh(seeded)
    assert verify_password("new-password-456", seeded.hashed_password)
    assert not verify_password("old-password-123", seeded.hashed_password)


def test_change_password_wrong_current_returns_400(api_client, db_session):
    seeded = _seed_user(db_session, username=f"pwuser2-{uuid.uuid4().hex[:8]}", password="correct-password")
    hdr = {"Authorization": f"Bearer {user_token(str(seeded.id))}"}

    r = api_client.post("/auth/me/password", json={
        "current_password": "wrong-password",
        "new_password": "irrelevant",
    }, headers=hdr)
    assert r.status_code == 400


def test_link_google_conflict_when_already_in_use_by_another_account(api_client, db_session):
    other = _seed_user(db_session, google_id="taken-google-id")
    seeded = _seed_user(db_session)
    hdr = {"Authorization": f"Bearer {user_token(str(seeded.id))}"}

    r = api_client.post("/auth/me/link-google", json={"google_id": other.google_id}, headers=hdr)
    assert r.status_code == 409
