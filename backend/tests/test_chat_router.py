import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def make_mock_redis():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.aclose = AsyncMock()
    return redis


def make_stream_chunks(text="hello world"):
    content = f'data: {{"choices":[{{"delta":{{"content":"{text}"}}}}]}}\n\n'.encode()
    done = b"data: [DONE]\n\n"

    async def _gen(*args, **kwargs):
        yield content
        yield done

    return _gen


def guest_headers(guest_id="test-guest-id"):
    """Every in-scope endpoint now requires a valid token (018-public-api-auth) — build a
    guest access token directly rather than round-tripping through POST /auth/guest."""
    from backend.services.auth_service import create_guest_access_token
    return {"Authorization": f"Bearer {create_guest_access_token(guest_id)}"}


def test_chat_completions_returns_streaming_response():
    from backend.main import app

    mock_redis = make_mock_redis()

    # `with TestClient(app) as client:` runs the ASGI lifespan (backend/main.py),
    # which is what creates app.state.http_client that ChatCompletionService needs.
    with TestClient(app) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch(
                "backend.routers.chat.ChatCompletionService.stream_completions",
                new=make_stream_chunks("test reply"),
            ),
        ):
            response = client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers=guest_headers(),
            )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_chat_completions_no_token_returns_401():
    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_chat_completions_rate_limit_exceeded_returns_429():
    from backend.main import app

    client = TestClient(app)
    mock_redis = make_mock_redis()
    mock_redis.incr = AsyncMock(return_value=100)

    with patch("backend.routers.chat._make_redis", return_value=mock_redis):
        response = client.post(
            "/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
            headers=guest_headers(),
        )

    assert response.status_code == 429
    data = response.json()
    assert "limit" in data["detail"]


def test_chat_completions_admin_bypasses_rate_limit():
    from backend.main import app
    from backend.tests.conftest import make_admin_token

    mock_redis = make_mock_redis()
    token = make_admin_token()

    with TestClient(app) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch(
                "backend.routers.chat.ChatCompletionService.stream_completions",
                new=make_stream_chunks(),
            ),
        ):
            response = client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 200
    mock_redis.incr.assert_not_called()


def test_chat_completions_x_topic_id_forwarded_to_stream():
    from backend.main import app

    mock_redis = make_mock_redis()
    captured_topic_id = []

    async def capturing_stream(self, messages, topic_id=None, pinned_article_ids=None):
        captured_topic_id.append(topic_id)
        yield b"data: [DONE]\n\n"

    with TestClient(app) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch(
                "backend.routers.chat.ChatCompletionService.stream_completions",
                new=capturing_stream,
            ),
        ):
            client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers={**guest_headers(), "X-Topic-Id": "topic-uuid-123"},
            )

    assert captured_topic_id == ["topic-uuid-123"]


def test_chat_completions_x_pinned_article_ids_forwarded_to_stream():
    from backend.main import app

    mock_redis = make_mock_redis()
    captured_pinned = []

    async def capturing_stream(self, messages, topic_id=None, pinned_article_ids=None):
        captured_pinned.append(pinned_article_ids)
        yield b"data: [DONE]\n\n"

    with TestClient(app) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch(
                "backend.routers.chat.ChatCompletionService.stream_completions",
                new=capturing_stream,
            ),
        ):
            client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers={**guest_headers(), "X-Pinned-Article-Ids": "uuid-1,uuid-2,uuid-3"},
            )

    assert captured_pinned == [["uuid-1", "uuid-2", "uuid-3"]]


def test_chat_completions_x_pinned_article_ids_trims_whitespace():
    from backend.main import app

    mock_redis = make_mock_redis()
    captured_pinned = []

    async def capturing_stream(self, messages, topic_id=None, pinned_article_ids=None):
        captured_pinned.append(pinned_article_ids)
        yield b"data: [DONE]\n\n"

    with TestClient(app) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch(
                "backend.routers.chat.ChatCompletionService.stream_completions",
                new=capturing_stream,
            ),
        ):
            client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers={**guest_headers(), "X-Pinned-Article-Ids": " uuid-1 , uuid-2 "},
            )

    assert captured_pinned == [["uuid-1", "uuid-2"]]


def test_chat_completions_no_x_pinned_article_ids_passes_none():
    from backend.main import app

    mock_redis = make_mock_redis()
    captured_pinned = []

    async def capturing_stream(self, messages, topic_id=None, pinned_article_ids=None):
        captured_pinned.append(pinned_article_ids)
        yield b"data: [DONE]\n\n"

    with TestClient(app) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch(
                "backend.routers.chat.ChatCompletionService.stream_completions",
                new=capturing_stream,
            ),
        ):
            client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers=guest_headers(),
            )

    assert captured_pinned == [None]


def test_guest_token_guest_id_used_as_rate_limit_key():
    from backend.main import app

    mock_redis = make_mock_redis()

    with TestClient(app) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch(
                "backend.routers.chat.ChatCompletionService.stream_completions",
                new=make_stream_chunks(),
            ),
        ):
            client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers=guest_headers(guest_id="known-guest-id"),
            )

    key_used = mock_redis.incr.call_args[0][0]
    assert "known-guest-id" in key_used


def test_stream_exception_yields_error_event_before_done():
    from backend.main import app

    mock_redis = make_mock_redis()

    async def failing_stream(self, messages, topic_id=None, pinned_article_ids=None):
        raise RuntimeError("upstream failure")
        yield

    with TestClient(app, raise_server_exceptions=False) as client:
        with (
            patch("backend.routers.chat._make_redis", return_value=mock_redis),
            patch("backend.routers.chat.ChatCompletionService.stream_completions", new=failing_stream),
        ):
            response = client.post(
                "/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers=guest_headers(),
            )

    assert response.status_code == 200
    body = response.content.decode()
    assert '"code": "EXTERNAL_DEPENDENCY_ERROR"' in body
    assert '"message": "An upstream dependency is unavailable"' in body
    assert "data: [DONE]" in body


def test_missing_exp_claim_returns_401():
    from backend.main import app
    from jose import jwt

    client = TestClient(app)
    token = jwt.encode({"sub": "user-1", "role": "user"}, "test-secret", algorithm="HS256")

    response = client.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_expired_token_returns_401():
    from backend.main import app
    from jose import jwt

    client = TestClient(app)
    token = jwt.encode(
        {"sub": "user-1", "role": "user", "exp": int(time.time()) - 3600},
        "test-secret",
        algorithm="HS256",
    )

    response = client.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


# ── /chat/quota ───────────────────────────────────────────────────────────────


def make_quota_redis(count=0):
    redis = make_mock_redis()
    redis.get = AsyncMock(return_value=str(count).encode() if count else None)
    return redis


def test_chat_quota_no_token_returns_401():
    from backend.main import app

    client = TestClient(app)
    response = client.get("/chat/quota")

    assert response.status_code == 401


def test_chat_quota_guest_returns_remaining():
    from backend.main import app

    client = TestClient(app)
    mock_redis = make_quota_redis(count=1)

    with patch("backend.routers.chat._make_redis", return_value=mock_redis):
        response = client.get("/chat/quota", headers=guest_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "guest"
    assert "remaining" in data
    assert "limit" in data
    assert data["limit"] > 0


def test_chat_quota_user_returns_user_tier():
    from backend.main import app
    from backend.tests.conftest import make_user_token

    client = TestClient(app)
    mock_redis = make_quota_redis()
    token = make_user_token()

    with patch("backend.routers.chat._make_redis", return_value=mock_redis):
        response = client.get(
            "/chat/quota",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["tier"] == "user"


def test_chat_quota_admin_returns_unlimited():
    from backend.main import app
    from backend.tests.conftest import make_admin_token

    client = TestClient(app)
    mock_redis = make_quota_redis()
    token = make_admin_token()

    with patch("backend.routers.chat._make_redis", return_value=mock_redis):
        response = client.get(
            "/chat/quota",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "admin"
    assert data["remaining"] == -1


def test_make_redis_builds_client_from_configured_url():
    from backend.routers.chat import _make_redis

    with patch("redis.asyncio.from_url") as mock_from_url:
        _make_redis()

    mock_from_url.assert_called_once()


def test_chat_quota_guest_id_used_as_rate_limit_key():
    from backend.main import app

    client = TestClient(app)
    mock_redis = make_quota_redis(count=2)

    with patch("backend.routers.chat._make_redis", return_value=mock_redis):
        client.get("/chat/quota", headers=guest_headers(guest_id="known-guest-id"))

    key_used = mock_redis.get.call_args[0][0]
    assert "known-guest-id" in key_used
