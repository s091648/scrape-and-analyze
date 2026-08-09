# backend/tests/test_graph.py
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


# Stable UUIDs for mock group definitions
_DT_UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_AI_UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")

_GROUP_NAME_TO_UUID = {
    'digital_twin': _DT_UUID,
    'ai_ml': _AI_UUID,
}


def _make_mock_db():
    """Create a mock DB session for tests that need AnalysesTranslation queries."""
    mock_db = MagicMock()
    # db.query(AnalysesTranslation).filter(...).all() → returns empty list
    mock_db.query.return_value.filter.return_value.all.return_value = []
    return mock_db


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
    analysis.id = uuid.uuid4()
    return analysis


_MOCK_GROUP_DEFS = {
    _DT_UUID: {'name': 'digital_twin', 'display_name': 'Digital Twin', 'color_hex': '#6366f1'},
    _AI_UUID: {'name': 'ai_ml', 'display_name': 'AI & Machine Learning', 'color_hex': '#f59e0b'},
}


def _mock_group_def(name='digital_twin', display='Digital Twin'):
    m = MagicMock()
    m.display_name = display
    m.id = _GROUP_NAME_TO_UUID.get(name, uuid.uuid4())
    return m


def test_graph_returns_nodes_and_edges():
    from backend.main import app
    client = _AuthedClient(app)
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
    client = _AuthedClient(app)
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
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?days=30')
    group_nodes = [n for n in response.json()['nodes'] if n['type'] == 'group']
    assert len(group_nodes) == 1
    assert group_nodes[0]['color'] == '#6366f1'
    assert group_nodes[0]['articleCount'] == 1


def test_graph_different_days_different_cache():
    from backend.main import app
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses) as mock_q, \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        client.get('/analyses/graph?aggregator=techcrunch')
        client.get('/analyses/graph?aggregator=arxiv')
    assert mock_q.call_count == 2


def test_graph_group_endpoint_returns_articles():
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica', 'model fidelity']}])]
    mock_db = _make_mock_db()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=mock_analyses), \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
            response = client.get('/analyses/graph/group/digital_twin')
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]['groupName'] == 'digital_twin'
    assert 'virtual replica' in items[0]['tags']


def test_graph_group_excerpt_max_200_chars():
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)
    mock_analysis = make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])
    mock_analysis.article.content = 'x' * 500
    mock_db = _make_mock_db()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=[mock_analysis]), \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
            response = client.get('/analyses/graph/group/digital_twin')
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert len(response.json()[0]['excerpt']) <= 200


def test_graph_group_guest_token_is_sufficient():
    """018-public-api-auth: no longer fully public — a guest token (not a real
    login) is sufficient, but *some* valid token is now required."""
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)
    mock_db = _make_mock_db()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=[]), \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
            response = client.get('/analyses/graph/group/any')
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200


def test_graph_group_requires_at_least_a_guest_token():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    mock_db = _make_mock_db()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get('/analyses/graph/group/any')
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 401


class _InMemoryFakeCacheGateway:
    """Minimal in-memory CacheGateway stand-in for hermetic unit tests — real cache-aside
    behavior (Redis-backed) is covered by backend/tests/integration/test_graph.py; this test
    only needs to confirm get_graph() actually calls through CacheGateway.get_or_set()."""

    def __init__(self):
        self._store = {}

    def get_or_set(self, namespace, params, ttl_seconds, loader, lang="en"):
        import json
        from shared.cache import CacheResult
        key = (namespace, lang, json.dumps(params, sort_keys=True, default=str))
        if key not in self._store:
            self._store[key] = loader()
            return CacheResult(value=self._store[key], status="MISS")
        return CacheResult(value=self._store[key], status="HIT")

    def bump_version(self, namespace):
        return 0


def test_graph_cache_hit_avoids_second_query():
    from backend.main import app
    from backend.cache import get_cache_gateway
    client = _AuthedClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    fake_gateway = _InMemoryFakeCacheGateway()
    app.dependency_overrides[get_cache_gateway] = lambda: fake_gateway
    try:
        with patch('backend.routers.graph.query_analyses', return_value=mock_analyses) as mock_q, \
             patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
            client.get('/analyses/graph')
            client.get('/analyses/graph')  # same params → cache hit
    finally:
        app.dependency_overrides.pop(get_cache_gateway, None)
    assert mock_q.call_count == 1


def test_graph_group_skips_analysis_without_article():
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)

    analysis_no_article = MagicMock()
    analysis_no_article.id = uuid.uuid4()
    analysis_no_article.article = None
    analysis_no_article.article_id = uuid.uuid4()

    mock_db = _make_mock_db()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=[analysis_no_article]), \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
            response = client.get('/analyses/graph/group/digital_twin')
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == []


def test_graph_group_uses_en_translation_fallback():
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)

    analysis = make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])

    en_trans = MagicMock()
    en_trans.analysis_id = analysis.id
    en_trans.language = "en"
    en_trans.pain_points = ["cost"]
    en_trans.insights = ["efficiency"]
    en_trans.innovations = ["new approach"]

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [en_trans]
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=[analysis]), \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
            response = client.get('/analyses/graph/group/digital_twin?lang=zh-TW')
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    item = response.json()[0]
    # No zh-TW translation → falls back to en
    assert item['pain_points'] == ["cost"]
    assert item['insights'] == ["efficiency"]


def test_graph_group_uses_lang_translation_when_present():
    from backend.main import app
    from backend.database import get_db
    client = _AuthedClient(app)

    analysis = make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])

    zh_trans = MagicMock()
    zh_trans.analysis_id = analysis.id
    zh_trans.language = "zh-TW"
    zh_trans.pain_points = ["成本"]
    zh_trans.insights = ["效率"]
    zh_trans.innovations = ["新方法"]

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [zh_trans]
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch('backend.routers.graph.query_group_articles', return_value=[analysis]), \
             patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
            response = client.get('/analyses/graph/group/digital_twin?lang=zh-TW')
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    item = response.json()[0]
    assert item['pain_points'] == ["成本"]
