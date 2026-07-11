"""
Integration tests for /articles endpoints.

Unit tests mock all DB calls.  These tests exercise the real SQL:
  - pagination offset arithmetic
  - source IN-filter
  - tag JOIN through article_tags
  - date-range filters
  - sort order
  - /filters/sources and /filters/tags distinct queries
  - article detail with tag_groups
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _article(source="techcrunch", title="Test", days_ago=0, topic_id=None):
    from models.article import Article
    return Article(
        id=uuid.uuid4(),
        url=f"https://example.com/{uuid.uuid4().hex}",
        url_hash=uuid.uuid4().hex,
        source=source,
        title=title,
        content="body",
        correlation_id=uuid.uuid4(),
        scraped_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        published_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        topic_id=topic_id,
    )


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_articles_empty(api_client):
    r = api_client.get("/articles")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_articles_pagination_total_and_page_size(db_session, api_client):
    for i in range(5):
        db_session.add(_article(title=f"Art {i}"))
    db_session.flush()

    r = api_client.get("/articles?page=1&size=2")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["size"] == 2


def test_articles_second_page_offset(db_session, api_client):
    for i in range(5):
        db_session.add(_article(title=f"Page {i}"))
    db_session.flush()

    r = api_client.get("/articles?page=2&size=3")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2  # 5 total, 3 on page 1 → 2 on page 2


def test_articles_beyond_last_page(db_session, api_client):
    db_session.add(_article())
    db_session.flush()

    r = api_client.get("/articles?page=99&size=10")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"] == []


# ---------------------------------------------------------------------------
# Source filter
# ---------------------------------------------------------------------------

def test_articles_filter_by_source(db_session, api_client):
    db_session.add(_article(source="arxiv"))
    db_session.add(_article(source="arxiv"))
    db_session.add(_article(source="techcrunch"))
    db_session.flush()

    r = api_client.get("/articles?source=arxiv")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert all(item["source"] == "arxiv" for item in data["items"])


def test_articles_filter_by_multiple_sources(db_session, api_client):
    db_session.add(_article(source="arxiv"))
    db_session.add(_article(source="techcrunch"))
    db_session.add(_article(source="wired"))
    db_session.flush()

    r = api_client.get("/articles?source=arxiv&source=wired")
    assert r.status_code == 200
    sources = {item["source"] for item in r.json()["items"]}
    assert sources == {"arxiv", "wired"}


# ---------------------------------------------------------------------------
# Tag filter  (JOIN through article_tags)
# ---------------------------------------------------------------------------

def _seed_tag(db_session, tag_name="ml"):
    from models.tag import Tag
    tag = Tag(id=uuid.uuid4(), name=tag_name)
    db_session.add(tag)
    db_session.flush()
    return tag


def _link(db_session, article, tag):
    from models.tag import article_tags
    db_session.execute(article_tags.insert().values(article_id=article.id, tag_id=tag.id))
    db_session.flush()


def test_articles_filter_by_tag(db_session, api_client):
    tag = _seed_tag(db_session, "deep-learning")
    tagged = _article(title="Tagged")
    untagged = _article(title="Untagged")
    db_session.add(tagged)
    db_session.add(untagged)
    db_session.flush()
    _link(db_session, tagged, tag)

    r = api_client.get("/articles?tag=deep-learning")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Tagged"


def test_articles_filter_by_two_tags_intersection(db_session, api_client):
    t1 = _seed_tag(db_session, "transformer")
    t2 = _seed_tag(db_session, "attention")

    both = _article(title="Both tags")
    one = _article(title="One tag")
    db_session.add(both)
    db_session.add(one)
    db_session.flush()
    _link(db_session, both, t1)
    _link(db_session, both, t2)
    _link(db_session, one, t1)

    r = api_client.get("/articles?tag=transformer&tag=attention")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Both tags"


# ---------------------------------------------------------------------------
# Date-range filter
# ---------------------------------------------------------------------------

def test_articles_filter_published_after(db_session, api_client):
    db_session.add(_article(title="Old", days_ago=10))
    db_session.add(_article(title="New", days_ago=1))
    db_session.flush()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
    r = api_client.get(f"/articles?published_after={cutoff}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "New"


def test_articles_filter_published_before(db_session, api_client):
    db_session.add(_article(title="Old", days_ago=10))
    db_session.add(_article(title="New", days_ago=1))
    db_session.flush()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
    r = api_client.get(f"/articles?published_before={cutoff}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Old"


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def test_articles_sort_scraped_at_asc(db_session, api_client):
    db_session.add(_article(title="Old", days_ago=5))
    db_session.add(_article(title="New", days_ago=0))
    db_session.flush()

    r = api_client.get("/articles?sort=scraped_at&order=asc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["title"] == "Old"
    assert items[-1]["title"] == "New"


def test_articles_sort_scraped_at_desc(db_session, api_client):
    db_session.add(_article(title="Old", days_ago=5))
    db_session.add(_article(title="New", days_ago=0))
    db_session.flush()

    r = api_client.get("/articles?sort=scraped_at&order=desc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["title"] == "New"
    assert items[-1]["title"] == "Old"


# ---------------------------------------------------------------------------
# /filters/sources  and  /filters/tags
# ---------------------------------------------------------------------------

def test_filter_sources_endpoint(db_session, api_client):
    db_session.add(_article(source="source_a"))
    db_session.add(_article(source="source_b"))
    db_session.add(_article(source="source_a"))  # duplicate — should be deduplicated
    db_session.flush()

    r = api_client.get("/articles/filters/sources")
    assert r.status_code == 200
    sources = r.json()
    assert "source_a" in sources
    assert "source_b" in sources
    assert sources.count("source_a") == 1  # distinct


def test_filter_tags_endpoint(db_session, api_client):
    t1 = _seed_tag(db_session, "rl")
    t2 = _seed_tag(db_session, "nlp")
    a = _article()
    db_session.add(a)
    db_session.flush()
    _link(db_session, a, t1)
    _link(db_session, a, t2)

    r = api_client.get("/articles/filters/tags")
    assert r.status_code == 200
    tags = r.json()
    assert "rl" in tags
    assert "nlp" in tags


# ---------------------------------------------------------------------------
# Article detail  (GET /articles/{id})
# ---------------------------------------------------------------------------

def test_article_detail_with_tags_and_group(db_session, api_client):
    from models.topic import Topic
    from models.tag_group import TagGroupDefinition

    topic = Topic(name=f"t-{uuid.uuid4().hex[:6]}", display_name="T",
                  color_hex="#000", sort_order=1)
    db_session.add(topic)
    db_session.flush()

    tg = TagGroupDefinition(name="vision", display_name="Vision",
                             color_hex="#3b82f6", sort_order=1, topic_id=topic.id)
    db_session.add(tg)
    db_session.flush()

    from models.tag import Tag
    tag = Tag(name="image-classification", tag_group_id=tg.id)
    db_session.add(tag)
    a = _article(title="CV Paper")
    db_session.add(a)
    db_session.flush()
    _link(db_session, a, tag)

    r = api_client.get(f"/articles/{a.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "CV Paper"
    assert "image-classification" in data["tags"]
    assert len(data["tag_groups"]) == 1
    assert data["tag_groups"][0]["group_name"] == "vision"
    assert data["tag_groups"][0]["display_name"] == "Vision"


def test_article_detail_not_found(api_client):
    r = api_client.get(f"/articles/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Recommendation signals: citation_count / view_count (spec 014)
# ---------------------------------------------------------------------------

def _seed_metrics(db_session, article, *, view_count=0, citation_count=None):
    from models.article_metrics import ArticleMetrics
    from models.article_metric_value import ArticleMetricValue

    db_session.add(ArticleMetrics(article_id=article.id, view_count=view_count))
    if citation_count is not None:
        db_session.add(ArticleMetricValue(
            article_id=article.id, metric_key="citation_count", value=citation_count,
        ))
    db_session.flush()


def test_articles_list_includes_citation_and_view_count(db_session, api_client):
    a = _article(title="With metrics")
    db_session.add(a)
    db_session.flush()
    _seed_metrics(db_session, a, view_count=42, citation_count=17)

    r = api_client.get("/articles")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["citation_count"] == 17
    assert item["view_count"] == 42


def test_articles_list_citation_count_null_and_view_count_zero_when_no_metrics_row(db_session, api_client):
    db_session.add(_article(title="No metrics"))
    db_session.flush()

    r = api_client.get("/articles")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["citation_count"] is None
    assert item["view_count"] == 0


def test_articles_sort_by_citation_count_desc(db_session, api_client):
    low = _article(title="Low citations")
    high = _article(title="High citations")
    db_session.add(low)
    db_session.add(high)
    db_session.flush()
    _seed_metrics(db_session, low, citation_count=2)
    _seed_metrics(db_session, high, citation_count=99)

    r = api_client.get("/articles?sort=citation_count&order=desc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["title"] == "High citations"
    assert items[-1]["title"] == "Low citations"


def test_articles_sort_by_view_count_desc(db_session, api_client):
    few = _article(title="Few views")
    many = _article(title="Many views")
    db_session.add(few)
    db_session.add(many)
    db_session.flush()
    _seed_metrics(db_session, few, view_count=1)
    _seed_metrics(db_session, many, view_count=500)

    r = api_client.get("/articles?sort=view_count&order=desc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["title"] == "Many views"
    assert items[-1]["title"] == "Few views"


def test_article_detail_includes_citation_and_view_count(db_session, api_client):
    a = _article(title="Detail metrics")
    db_session.add(a)
    db_session.flush()
    _seed_metrics(db_session, a, view_count=7, citation_count=3)

    r = api_client.get(f"/articles/{a.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["citation_count"] == 3
    assert data["view_count"] == 7


def test_article_detail_citation_count_null_when_no_metric_value(db_session, api_client):
    a = _article(title="No citation row")
    db_session.add(a)
    db_session.flush()
    _seed_metrics(db_session, a, view_count=0, citation_count=None)

    r = api_client.get(f"/articles/{a.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["citation_count"] is None
    assert data["view_count"] == 0
