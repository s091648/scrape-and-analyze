# backend/tests/test_graph.py
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def make_mock_tag(name, group_name):
    t = MagicMock()
    t.name = name
    t.tag_group_name = group_name
    return t


def make_mock_analysis(tag_groups):
    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = "Test Article"
    article.source = "techcrunch"
    article.url = "https://example.com"
    article.content = "Article content here for testing."
    article.published_at = None
    article.tags = [
        make_mock_tag(tag_name, tg['group'])
        for tg in tag_groups
        for tag_name in tg.get('tags', [])
    ]
    analysis = MagicMock()
    analysis.article = article
    analysis.article_id = article.id
    analysis.pain_points = "Some pain points"
    analysis.insights = "Some insights"
    analysis.innovations = "Some innovations"
    return analysis


_MOCK_GROUP_DEFS = {
    'digital_twin': {'display_name': 'Digital Twin', 'color_hex': '#6366f1'},
    'ai_ml': {'display_name': 'AI & Machine Learning', 'color_hex': '#f59e0b'},
}


def _mock_group_def(name='digital_twin', display='Digital Twin'):
    m = MagicMock()
    m.display_name = display
    return m


def test_graph_returns_nodes_and_edges():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?days=30')
    assert response.status_code == 200
    data = response.json()
    assert 'nodes' in data
    assert 'edges' in data


def test_graph_contains_group_and_article_nodes():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?days=30')
    nodes = response.json()['nodes']
    node_types = {n['type'] for n in nodes}
    assert 'group' in node_types
    assert 'article' in node_types


def test_graph_group_node_has_color_and_count():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?days=30')
    group_nodes = [n for n in response.json()['nodes'] if n['type'] == 'group']
    assert len(group_nodes) == 1
    assert group_nodes[0]['color'] == '#6366f1'
    assert group_nodes[0]['articleCount'] == 1


def test_graph_different_days_different_cache():
    import backend.routers.graph as graph_module
    graph_module._cache.clear()
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses) as mock_q, \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        client.get('/analyses/graph?days=30')
        client.get('/analyses/graph?days=90')
    assert mock_q.call_count == 2


def test_graph_group_endpoint_returns_articles():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica', 'model fidelity']}])]
    with patch('backend.routers.graph.query_group_articles', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
        response = client.get('/analyses/graph/group/digital_twin')
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]['groupName'] == 'digital_twin'
    assert 'virtual replica' in items[0]['tags']


def test_graph_group_excerpt_max_200_chars():
    from backend.main import app
    client = TestClient(app)
    mock_analysis = make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])
    mock_analysis.article.content = 'x' * 500
    with patch('backend.routers.graph.query_group_articles', return_value=[mock_analysis]), \
         patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
        response = client.get('/analyses/graph/group/digital_twin')
    assert len(response.json()[0]['excerpt']) <= 200


def test_graph_group_no_auth_required():
    from backend.main import app
    client = TestClient(app)
    with patch('backend.routers.graph.query_group_articles', return_value=[]), \
         patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
        response = client.get('/analyses/graph/group/any')
    assert response.status_code == 200
