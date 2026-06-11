import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


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


def test_chat_completions_returns_streaming_response():
    from backend.main import app

    client = TestClient(app)
    mock_redis = make_mock_redis()

    with (
        patch("backend.routers.chat._make_redis", return_value=mock_redis),
        patch(
            "backend.routers.chat.ChatService.stream_completions",
            new=make_stream_chunks("test reply"),
        ),
    ):
        response = client.post(
            "/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_chat_completions_rate_limit_exceeded_returns_429():
    from backend.main import app

    client = TestClient(app)
    mock_redis = make_mock_redis()
    mock_redis.incr = AsyncMock(return_value=100)

    with patch("backend.routers.chat._make_redis", return_value=mock_redis):
        response = client.post(
            "/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

    assert response.status_code == 429
    data = response.json()
    assert "limit" in data["detail"]


def test_chat_completions_admin_bypasses_rate_limit():
    from backend.main import app
    from backend.tests.conftest import make_admin_token

    client = TestClient(app)
    mock_redis = make_mock_redis()
    token = make_admin_token()

    with (
        patch("backend.routers.chat._make_redis", return_value=mock_redis),
        patch(
            "backend.routers.chat.ChatService.stream_completions",
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

    client = TestClient(app)
    mock_redis = make_mock_redis()
    captured_topic_id = []

    async def capturing_stream(self, messages, topic_id=None):
        captured_topic_id.append(topic_id)
        yield b"data: [DONE]\n\n"

    with (
        patch("backend.routers.chat._make_redis", return_value=mock_redis),
        patch(
            "backend.routers.chat.ChatService.stream_completions",
            new=capturing_stream,
        ),
    ):
        client.post(
            "/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
            headers={"X-Topic-Id": "topic-uuid-123"},
        )

    assert captured_topic_id == ["topic-uuid-123"]


def test_guest_first_visit_sets_rag_gid_cookie():
    from backend.main import app

    client = TestClient(app, raise_server_exceptions=False)
    mock_redis = make_mock_redis()

    with (
        patch("backend.routers.chat._make_redis", return_value=mock_redis),
        patch(
            "backend.routers.chat.ChatService.stream_completions",
            new=make_stream_chunks(),
        ),
    ):
        response = client.post(
            "/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

    assert response.status_code == 200
    assert "__rag_gid" in response.cookies


def test_guest_with_existing_cookie_uses_cookie_id():
    from backend.main import app

    client = TestClient(app)
    mock_redis = make_mock_redis()

    with (
        patch("backend.routers.chat._make_redis", return_value=mock_redis),
        patch(
            "backend.routers.chat.ChatService.stream_completions",
            new=make_stream_chunks(),
        ),
    ):
        client.post(
            "/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
            cookies={"__rag_gid": "existing-cookie-uuid"},
        )

    key_used = mock_redis.incr.call_args[0][0]
    assert "existing-cookie-uuid" in key_used
