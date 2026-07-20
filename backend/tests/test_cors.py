import importlib

import pytest


@pytest.fixture
def app_with_frontend_origin(monkeypatch):
    """Reload backend.config then backend.main after setting FRONTEND_ORIGIN so CORSMiddleware
    picks up the test value. FRONTEND_ORIGIN is only read once, at backend/config.py's own
    import time — by the time this test runs, some earlier test file has very likely already
    imported backend.config (and baked in whatever FRONTEND_ORIGIN came from the process env,
    e.g. docker-compose's `.env`), so just setting the env var here has no effect without a
    reload. backend.main does `from backend.config import FRONTEND_ORIGIN`, which only re-binds
    to backend.config's *current* attribute value on reload — so backend.config must be reloaded
    first, then backend.main, in that order. Reloads back afterward so later tests see the
    process's real FRONTEND_ORIGIN again instead of this test's value."""
    def _set(origin: str):
        monkeypatch.setenv("FRONTEND_ORIGIN", origin)
        import backend.config as config
        importlib.reload(config)
        import backend.main as main
        importlib.reload(main)
        return main.app

    yield _set

    monkeypatch.undo()
    import backend.config as config
    importlib.reload(config)
    import backend.main as main
    importlib.reload(main)


def test_cors_allowed_origin(app_with_frontend_origin):
    app = app_with_frontend_origin("http://localhost:3000")
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_blocked_origin(app_with_frontend_origin):
    app = app_with_frontend_origin("http://localhost:3000")
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"}
    )
    assert response.headers.get("access-control-allow-origin") != "http://evil.com"
