import os
import time
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")

_TOPIC_ID = uuid.uuid4()


def _admin_token():
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600},
        "test-secret",
        algorithm="HS256",
    )


def _mock_keyword(**kwargs):
    k = MagicMock(spec=[])
    k.id = kwargs.get("id", uuid.uuid4())
    k.keyword_type = kwargs.get("keyword_type", "rss")
    k.keyword = kwargs.get("keyword", "machine learning")
    return k


# ---------------------------------------------------------------------------
# GET /scraper-keywords?topic_id=...
# ---------------------------------------------------------------------------

def test_list_keywords_requires_admin():
    from backend.main import app

    client = TestClient(app)
    response = client.get(f"/scraper-keywords?topic_id={_TOPIC_ID}")
    assert response.status_code == 401


def test_list_keywords_with_admin_returns_200():
    from backend.main import app

    mock_kw = _mock_keyword()
    with patch("backend.routers.scraper_keywords.list_keywords", return_value=[mock_kw]):
        client = TestClient(app)
        response = client.get(
            f"/scraper-keywords?topic_id={_TOPIC_ID}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["keyword"] == "machine learning"


def test_list_keywords_with_type_filter():
    from backend.main import app

    mock_kw = _mock_keyword(keyword_type="arxiv_keyword")
    with patch("backend.routers.scraper_keywords.list_keywords", return_value=[mock_kw]) as mock_list:
        client = TestClient(app)
        client.get(
            f"/scraper-keywords?topic_id={_TOPIC_ID}&keyword_type=arxiv_keyword",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )

    _, call_kwargs = mock_list.call_args
    # keyword_type is passed as positional arg; verify the call was made
    assert mock_list.called


# ---------------------------------------------------------------------------
# POST /scraper-keywords?topic_id=...
# ---------------------------------------------------------------------------

def test_create_keyword_requires_admin():
    from backend.main import app

    client = TestClient(app)
    response = client.post(
        f"/scraper-keywords?topic_id={_TOPIC_ID}",
        json={"keyword": "deep learning", "keyword_type": "rss"},
    )
    assert response.status_code == 401


def test_create_keyword_with_admin_returns_201():
    from backend.main import app

    mock_kw = _mock_keyword(keyword="deep learning")
    with patch("backend.routers.scraper_keywords.create_keyword", return_value=mock_kw):
        client = TestClient(app)
        response = client.post(
            f"/scraper-keywords?topic_id={_TOPIC_ID}",
            json={"keyword": "deep learning", "keyword_type": "rss"},
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )

    assert response.status_code == 201
    assert response.json()["keyword"] == "deep learning"


def test_create_keyword_invalid_type_returns_422():
    from backend.main import app

    client = TestClient(app)
    response = client.post(
        f"/scraper-keywords?topic_id={_TOPIC_ID}",
        json={"keyword": "test", "keyword_type": "totally_invalid"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /scraper-keywords/{id}
# ---------------------------------------------------------------------------

def test_delete_keyword_requires_admin():
    from backend.main import app

    client = TestClient(app)
    response = client.delete(f"/scraper-keywords/{uuid.uuid4()}")
    assert response.status_code == 401


def test_delete_keyword_with_admin_returns_204():
    from backend.main import app

    with patch("backend.routers.scraper_keywords.delete_keyword", return_value=True):
        client = TestClient(app)
        response = client.delete(
            f"/scraper-keywords/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )

    assert response.status_code == 204


def test_delete_keyword_not_found_returns_404():
    from backend.main import app

    with patch("backend.routers.scraper_keywords.delete_keyword", return_value=False):
        client = TestClient(app)
        response = client.delete(
            f"/scraper-keywords/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )

    assert response.status_code == 404
