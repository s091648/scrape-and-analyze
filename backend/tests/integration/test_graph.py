"""
Integration tests for /analyses/graph endpoints.

Unit tests mock DB calls. These tests exercise real SQL:
  - /analyses/graph with and without seeded data
  - /analyses/graph/group/{name} article listing
  - graph_service pure functions called directly
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# Ensure these models are in Base.metadata before db_engine creates tables
from models.analyses_translation import AnalysesTranslation  # noqa: F401
from models.tag_group_translation import TagGroupDefinitionsTranslation  # noqa: F401
from models.tag_translation import TagsTranslation  # noqa: F401

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _topic(db_session, name=None):
    from models.topic import Topic
    t = Topic(
        id=uuid.uuid4(),
        name=name or f"t-{uuid.uuid4().hex[:6]}",
        display_name="Test Topic",
        color_hex="#000000",
        sort_order=1,
    )
    db_session.add(t)
    db_session.flush()
    return t


def _article(db_session, topic=None, source="arxiv", title="Test Article"):
    from models.article import Article
    a = Article(
        id=uuid.uuid4(),
        url=f"https://ex.com/{uuid.uuid4().hex}",
        url_hash=uuid.uuid4().hex,
        source=source,
        title=title,
        content="Article content " * 20,
        correlation_id=uuid.uuid4(),
        published_at=datetime.now(timezone.utc),
        topic_id=topic.id if topic else None,
    )
    db_session.add(a)
    db_session.flush()
    return a


def _analysis(db_session, article):
    from models.analysis import Analysis
    a = Analysis(
        id=uuid.uuid4(),
        article_id=article.id,
        correlation_id=uuid.uuid4(),
        model_used="test-model",
    )
    db_session.add(a)
    db_session.flush()
    return a


def _group(db_session, topic, name=None, color="#6366f1"):
    from models.tag_group import TagGroupDefinition
    name = name or f"grp-{uuid.uuid4().hex[:6]}"
    g = TagGroupDefinition(
        id=uuid.uuid4(),
        name=name,
        display_name=name.replace("-", " ").title(),
        color_hex=color,
        sort_order=1,
        topic_id=topic.id,
    )
    db_session.add(g)
    db_session.flush()
    return g


def _tag(db_session, name=None, group=None):
    from models.tag import Tag
    t = Tag(id=uuid.uuid4(), name=name or f"tag-{uuid.uuid4().hex[:6]}")
    if group:
        t.tag_group_id = group.id
    db_session.add(t)
    db_session.flush()
    return t


def _link(db_session, article, tag):
    from models.tag import article_tags
    db_session.execute(article_tags.insert().values(article_id=article.id, tag_id=tag.id))
    db_session.flush()


# ---------------------------------------------------------------------------
# GET /analyses/graph — empty state
# ---------------------------------------------------------------------------

def test_graph_empty_returns_empty_graph(api_client):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    r = api_client.get("/analyses/graph")
    assert r.status_code == 200
    data = r.json()
    assert data["nodes"] == []
    assert data["edges"] == []


# ---------------------------------------------------------------------------
# GET /analyses/graph — with seeded data
# ---------------------------------------------------------------------------

def test_graph_with_data_returns_nodes_and_edges(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="ai-ml")
    tag = _tag(db_session, name="transformer", group=grp)
    art = _article(db_session, topic)
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1


def test_graph_node_types_are_correct(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="vision")
    tag = _tag(db_session, name="cnn", group=grp)
    art = _article(db_session, topic)
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph")
    types = {n["type"] for n in r.json()["nodes"]}
    assert "article" in types
    assert "group" in types


def test_graph_group_node_has_color_and_count(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="robotics", color="#ff0000")
    tag = _tag(db_session, name="motion", group=grp)
    art = _article(db_session, topic)
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph")
    group_nodes = [n for n in r.json()["nodes"] if n["type"] == "group"]
    assert len(group_nodes) >= 1
    robot_node = next((n for n in group_nodes if n["groupName"] == "robotics"), None)
    assert robot_node is not None
    assert robot_node["color"] == "#ff0000"
    assert robot_node["articleCount"] == 1


def test_graph_article_node_has_label_and_id(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="some-group")
    tag = _tag(db_session, name="some-tag", group=grp)
    art = _article(db_session, topic, title="Unique Article Title")
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph")
    article_nodes = [n for n in r.json()["nodes"] if n["type"] == "article"]
    assert any(n["label"] == "Unique Article Title" for n in article_nodes)
    assert all("articleId" in n for n in article_nodes)


def test_graph_filters_by_topic_id(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic_a = _topic(db_session)
    topic_b = _topic(db_session)
    grp = _group(db_session, topic_a, name="grp-topic-a")
    tag = _tag(db_session, name="tag-a", group=grp)
    art_a = _article(db_session, topic_a)
    art_b = _article(db_session, topic_b)
    _analysis(db_session, art_a)
    _analysis(db_session, art_b)
    _link(db_session, art_a, tag)

    r = api_client.get(f"/analyses/graph?topic_id={topic_a.id}")
    article_ids = {n["articleId"] for n in r.json()["nodes"] if n["type"] == "article"}
    assert str(art_a.id) in article_ids
    assert str(art_b.id) not in article_ids


# ---------------------------------------------------------------------------
# GET /analyses/graph/group/{group_name}
# ---------------------------------------------------------------------------

def test_graph_group_empty_for_unknown_group(api_client):
    r = api_client.get("/analyses/graph/group/nonexistent-group")
    assert r.status_code == 200
    assert r.json() == []


def test_graph_group_returns_articles_for_group(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="nlp-field")
    tag = _tag(db_session, name="bert", group=grp)
    art = _article(db_session, topic, title="BERT Paper")
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph/group/nlp-field")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["groupName"] == "nlp-field"
    assert "bert" in items[0]["tags"]
    assert items[0]["title"] == "BERT Paper"


def test_graph_group_item_has_required_fields(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="field-check")
    tag = _tag(db_session, name="check-tag", group=grp)
    art = _article(db_session, topic)
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph/group/field-check")
    item = r.json()[0]
    for field in ("groupName", "displayName", "tags", "articleId", "title",
                  "source", "url", "excerpt", "pain_points", "insights", "innovations"):
        assert field in item, f"missing field: {field}"


def test_graph_group_excerpt_is_max_200_chars(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="truncate-test")
    tag = _tag(db_session, name="long-content", group=grp)
    art = _article(db_session, topic)
    art.content = "x" * 500
    db_session.flush()
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph/group/truncate-test")
    assert len(r.json()[0]["excerpt"]) <= 200


def test_graph_group_pain_points_none_without_translation(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="notrans-group")
    tag = _tag(db_session, name="notrans-tag", group=grp)
    art = _article(db_session, topic)
    _analysis(db_session, art)
    _link(db_session, art, tag)

    r = api_client.get("/analyses/graph/group/notrans-group")
    item = r.json()[0]
    assert item["pain_points"] is None
    assert item["insights"] is None
    assert item["innovations"] is None


def test_graph_group_filters_by_aggregator(api_client, db_session):
    import backend.routers.graph as graph_module
    graph_module._cache.clear()

    topic = _topic(db_session)
    grp = _group(db_session, topic, name="agg-filter")
    tag = _tag(db_session, name="agg-tag", group=grp)
    art_arxiv = _article(db_session, topic, source="arxiv")
    art_rss = _article(db_session, topic, source="rss")
    _analysis(db_session, art_arxiv)
    _analysis(db_session, art_rss)
    _link(db_session, art_arxiv, tag)
    _link(db_session, art_rss, tag)

    r = api_client.get("/analyses/graph/group/agg-filter?aggregator=arxiv")
    article_ids = {item["articleId"] for item in r.json()}
    assert str(art_arxiv.id) in article_ids
    assert str(art_rss.id) not in article_ids


# ---------------------------------------------------------------------------
# graph_service — pure function unit tests (no DB)
# ---------------------------------------------------------------------------

def test_build_graph_empty_input():
    from backend.services.graph_service import build_graph
    result = build_graph([], {})
    assert result == {"nodes": [], "edges": []}


def test_build_graph_creates_article_and_group_nodes():
    from backend.services.graph_service import build_graph

    group_id = uuid.uuid4()
    group_defs = {
        group_id: {"name": "ai", "display_name": "AI", "color_hex": "#fff"},
    }
    tag = MagicMock()
    tag.tag_group_id = group_id

    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = "Test Article"
    article.tags = [tag]

    analysis = MagicMock()
    analysis.article_id = article.id
    analysis.article = article

    result = build_graph([analysis], group_defs)
    types = {n["type"] for n in result["nodes"]}
    assert "article" in types
    assert "group" in types
    assert len(result["edges"]) == 1


def test_build_graph_deduplicates_articles():
    from backend.services.graph_service import build_graph

    group_id = uuid.uuid4()
    group_defs = {
        group_id: {"name": "topic", "display_name": "Topic", "color_hex": "#ccc"},
    }
    tag = MagicMock()
    tag.tag_group_id = group_id

    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = "Same Article"
    article.tags = [tag]

    analysis_a = MagicMock(article_id=article.id, article=article)
    analysis_b = MagicMock(article_id=article.id, article=article)

    result = build_graph([analysis_a, analysis_b], group_defs)
    article_nodes = [n for n in result["nodes"] if n["type"] == "article"]
    assert len(article_nodes) == 1


def test_build_graph_group_article_count():
    from backend.services.graph_service import build_graph

    group_id = uuid.uuid4()
    group_defs = {
        group_id: {"name": "counted", "display_name": "Counted", "color_hex": "#abc"},
    }

    def make_analysis():
        tag = MagicMock()
        tag.tag_group_id = group_id
        art = MagicMock()
        art.id = uuid.uuid4()
        art.title = "Art"
        art.tags = [tag]
        a = MagicMock()
        a.article_id = art.id
        a.article = art
        return a

    result = build_graph([make_analysis(), make_analysis()], group_defs)
    group_node = next(n for n in result["nodes"] if n["type"] == "group")
    assert group_node["articleCount"] == 2


def test_build_graph_skips_tag_without_group_def():
    from backend.services.graph_service import build_graph

    tag = MagicMock()
    tag.tag_group_id = uuid.uuid4()  # not in group_defs

    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = "No Group"
    article.tags = [tag]

    analysis = MagicMock(article_id=article.id, article=article)

    result = build_graph([analysis], {})
    assert len(result["nodes"]) == 1  # only article node, no group
    assert result["nodes"][0]["type"] == "article"
    assert result["edges"] == []
