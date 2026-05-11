import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


def make_mock_article():
    return MagicMock(
        id=uuid.uuid4(),
        url="https://example.com/article",
        source="techcrunch",
        title="Test Article",
        content="Content here",
        published_at=datetime.now(timezone.utc),
        scraped_at=datetime.now(timezone.utc),
    )


def test_articles_returns_paginated_envelope():
    from backend.main import app
    client = TestClient(app)
    mock_article = make_mock_article()
    with patch("backend.routers.articles.get_articles_paginated",
               return_value=(1, [mock_article])):
        response = client.get("/articles")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data


def test_articles_invalid_sort_returns_422():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/articles?sort=invalid_column")
    assert response.status_code == 422


def test_articles_no_auth_required():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.routers.articles.get_articles_paginated", return_value=(0, [])):
        response = client.get("/articles")
    assert response.status_code == 200


def test_article_detail_returns_full_data():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    article_id = uuid.uuid4()
    mock_article = make_mock_article()
    mock_article.id = article_id
    mock_analysis = MagicMock(id=uuid.uuid4(), model_used="claude")
    mock_article.analyses = [mock_analysis]

    mock_db = MagicMock()
    # Mock Tag.name query (for flat tags list)
    tag_result = MagicMock()
    tag_result.name = "test-tag"
    mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [(tag_result,)]
    # Mock AnalysesTranslation query (for content)
    mock_translation = MagicMock(pain_points="...", insights="...", innovations="...")
    # The query chain: db.query(AnalysesTranslation).filter(...).first()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_translation

    def override_get_db():
        yield mock_db

    with patch("backend.routers.articles.get_article_by_id", return_value=mock_article):
        app.dependency_overrides[get_db] = override_get_db
        try:
            response = client.get(f"/articles/{article_id}?lang=en")
        finally:
            app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    data = response.json()
    assert "tags" in data
    assert "tag_groups" in data


def test_article_detail_tag_groups_structure():
    from backend.main import app
    client = TestClient(app)
    article_id = uuid.uuid4()
    mock_article = make_mock_article()
    mock_article.id = article_id
    mock_article.analyses = []

    mock_tag = MagicMock()
    mock_tag.name = "digital twin"
    mock_tag.tag_group_name = "digital_twin"
    mock_tag.group_def = MagicMock(display_name="Digital Twin", color_hex="#3b82f6")
    mock_article.tags = [mock_tag]

    with patch("backend.routers.articles.get_article_by_id", return_value=mock_article):
        with patch("backend.routers.articles.get_tag_groups_for_article",
                   return_value=[{"group_name": "digital_twin", "display_name": "Digital Twin",
                                  "color": "#3b82f6", "tags": ["digital twin"]}]):
            response = client.get(f"/articles/{article_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["tag_groups"], list)


def test_article_detail_unknown_id_returns_404():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.routers.articles.get_article_by_id", return_value=None):
        response = client.get(f"/articles/{uuid.uuid4()}")
    assert response.status_code == 404
