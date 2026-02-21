import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def make_mock_analysis(tags):
    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = "Test Article"
    article.source = "techcrunch"
    article.url = "https://example.com"
    analysis = MagicMock()
    analysis.tags = tags
    analysis.article = article
    analysis.article_id = article.id
    return analysis


def test_graph_returns_nodes_and_edges():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis(["IoT", "digital twin"])]
    with patch("backend.routers.graph.query_analyses", return_value=mock_analyses):
        response = client.get("/analyses/graph?days=30")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data


def test_graph_contains_tag_and_article_nodes():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis(["IoT"])]
    with patch("backend.routers.graph.query_analyses", return_value=mock_analyses):
        response = client.get("/analyses/graph?days=30")
    nodes = response.json()["nodes"]
    node_types = {n["type"] for n in nodes}
    assert "tag" in node_types
    assert "article" in node_types


def test_graph_different_days_different_cache():
    import backend.routers.graph as graph_module
    graph_module._cache.clear()  # Ensure clean state for cache isolation test
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis(["IoT"])]
    with patch("backend.routers.graph.query_analyses", return_value=mock_analyses) as mock_q:
        client.get("/analyses/graph?days=30")
        client.get("/analyses/graph?days=90")
    assert mock_q.call_count == 2  # Different cache keys


def test_graph_tag_filters_articles():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis(["IoT", "AI"])]
    with patch("backend.routers.graph.query_tag_articles", return_value=mock_analyses):
        response = client.get("/analyses/graph/tag/IoT")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)


def test_graph_tag_excerpt_max_200_chars():
    from backend.main import app
    client = TestClient(app)
    mock_analysis = make_mock_analysis(["IoT"])
    mock_analysis.article.content = "x" * 500
    with patch("backend.routers.graph.query_tag_articles", return_value=[mock_analysis]):
        response = client.get("/analyses/graph/tag/IoT")
    item = response.json()[0]
    assert len(item["excerpt"]) <= 200


def test_graph_tag_no_auth_required():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.routers.graph.query_tag_articles", return_value=[]):
        response = client.get("/analyses/graph/tag/any")
    assert response.status_code == 200
