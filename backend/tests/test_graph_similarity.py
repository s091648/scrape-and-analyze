# backend/tests/test_graph_similarity.py
"""Additional tests for graph.py covering the include_similarity
and tag-based filtering added in feat/semantic_tag_mgr."""
import os
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def _guest_headers():
    from backend.services.auth_service import create_guest_access_token
    return {"Authorization": f"Bearer {create_guest_access_token('test-guest-id')}"}


class _AuthedClient:
    """018-public-api-auth: /analyses/graph* now requires a token — wrap TestClient
    so every .get() carries a guest token by default without editing every call site."""

    def __init__(self, app):
        self._client = TestClient(app)

    def get(self, url, **kwargs):
        kwargs["headers"] = {**_guest_headers(), **kwargs.get("headers", {})}
        return self._client.get(url, **kwargs)

    def __getattr__(self, name):
        return getattr(self._client, name)


_DT_UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_AI_UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
_ML_UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")

_GROUP_NAME_TO_UUID = {
    'digital_twin': _DT_UUID,
    'ai_ml': _AI_UUID,
    'machine_learning': _ML_UUID,
}

_MOCK_GROUP_DEFS = {
    _DT_UUID: {'name': 'digital_twin', 'display_name': 'Digital Twin', 'color_hex': '#6366f1'},
    _AI_UUID: {'name': 'ai_ml', 'display_name': 'AI & Machine Learning', 'color_hex': '#f59e0b'},
    _ML_UUID: {'name': 'machine_learning', 'display_name': 'Machine Learning', 'color_hex': '#10b981'},
}


def make_mock_tag(name, group_name):
    t = MagicMock()
    t.name = name
    t.tag_group_name = group_name
    t.tag_group_id = _GROUP_NAME_TO_UUID.get(group_name, uuid.uuid4())
    return t


def make_mock_analysis(tag_groups):
    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = "Test Article"
    article.source = "techcrunch"
    article.url = "https://example.com"
    article.content = "Article content here."
    article.published_at = None
    article.tags = [
        make_mock_tag(tag_name, tg['group'])
        for tg in tag_groups
        for tag_name in tg.get('tags', [])
    ]
    analysis = MagicMock()
    analysis.article = article
    analysis.article_id = article.id
    analysis.id = uuid.uuid4()
    return analysis


def _make_mock_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []
    return mock_db


def _mock_group_def(name='digital_twin', display='Digital Twin'):
    m = MagicMock()
    m.display_name = display
    m.id = _GROUP_NAME_TO_UUID.get(name, uuid.uuid4())
    return m


def test_graph_with_tag_filter():
    """Graph endpoint should pass tag filter to query_analyses."""
    import backend.routers.graph as graph_module
    graph_module._cache.clear()
    from backend.main import app
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'ai_ml', 'tags': ['llm']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses) as mock_q, \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?tag=llm')
    assert response.status_code == 200
    mock_q.assert_called_once()
    call_kwargs = mock_q.call_args
    assert 'llm' in call_kwargs.kwargs.get('tags', call_kwargs[1].get('tags', []))


def test_graph_with_topic_id_filter():
    """Graph endpoint should pass topic_id to query_analyses."""
    import backend.routers.graph as graph_module
    graph_module._cache.clear()
    from backend.main import app
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'ai_ml', 'tags': ['llm']}])]
    topic_id = str(uuid.uuid4())
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses) as mock_q, \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get(f'/analyses/graph?topic_id={topic_id}')
    assert response.status_code == 200
    call_kwargs = mock_q.call_args
    assert str(call_kwargs.kwargs.get('topic_id', call_kwargs[1].get('topic_id', ''))) == topic_id


def test_graph_caches_result():
    """Second request with same params should use cache."""
    import backend.routers.graph as graph_module
    graph_module._cache.clear()
    from backend.main import app
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses) as mock_q, \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        client.get('/analyses/graph?days=30')
        client.get('/analyses/graph?days=30')
    assert mock_q.call_count == 1


def test_graph_multiple_groups_same_article():
    """An article with tags from multiple groups should create edges to each group."""
    import backend.routers.graph as graph_module
    graph_module._cache.clear()
    from backend.main import app
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([
        {'group': 'digital_twin', 'tags': ['virtual replica']},
        {'group': 'ai_ml', 'tags': ['llm']},
    ])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph')
    data = response.json()
    group_nodes = [n for n in data['nodes'] if n['type'] == 'group']
    assert len(group_nodes) == 2
    edges_from_groups = [e for e in data['edges'] if e['source'].startswith('group:')]
    assert len(edges_from_groups) == 2


def test_graph_group_endpoint_with_tag_filter():
    """Group detail endpoint should support tag filtering."""
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)
    mock_analysis = make_mock_analysis([{'group': 'ai_ml', 'tags': ['llm', 'nlp']}])
    mock_db = _make_mock_db()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=[mock_analysis]) as mock_q, \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def('ai_ml', 'AI & ML')):
            response = client.get('/analyses/graph/group/ai_ml?tag=llm')
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    call_kwargs = mock_q.call_args
    assert 'llm' in call_kwargs.kwargs.get('tags', call_kwargs[1].get('tags', []))


def test_graph_group_endpoint_with_topic_id():
    """Group detail endpoint should pass topic_id."""
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)
    mock_db = _make_mock_db()
    topic_id = str(uuid.uuid4())

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=[]) as mock_q, \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
            response = client.get(f'/analyses/graph/group/digital_twin?topic_id={topic_id}')
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    call_kwargs = mock_q.call_args
    assert str(call_kwargs.kwargs.get('topic_id', call_kwargs[1].get('topic_id', ''))) == topic_id


def test_build_graph_with_missing_group_def():
    """Tags whose group_id is not in group_defs should be silently skipped."""
    from backend.routers.graph import build_graph
    unknown_uuid = uuid.uuid4()
    tag = MagicMock()
    tag.name = 'orphan'
    tag.tag_group_id = unknown_uuid
    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = 'Orphan Article'
    article.tags = [tag]
    analysis = MagicMock()
    analysis.article_id = article.id
    analysis.article = article

    result = build_graph([analysis], _MOCK_GROUP_DEFS)
    # No group node created for the unknown UUID
    group_nodes = [n for n in result['nodes'] if n['type'] == 'group']
    assert len(group_nodes) == 0
    # Article node still created
    article_nodes = [n for n in result['nodes'] if n['type'] == 'article']
    assert len(article_nodes) == 1
