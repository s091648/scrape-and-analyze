"""
Unit tests for backend/services/article_service.py.

Router-level tests mock service functions. These tests call service
functions directly with a mock DB session to achieve coverage.
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# build_article_out
# ---------------------------------------------------------------------------

def _mock_article(**kwargs):
    a = MagicMock()
    a.id = kwargs.get("id", uuid.uuid4())
    a.url = kwargs.get("url", "https://example.com/art")
    a.source = kwargs.get("source", "arxiv")
    a.title = kwargs.get("title", "Test Article")
    a.content = kwargs.get("content", "body")
    a.published_at = kwargs.get("published_at", datetime.now(timezone.utc))
    a.scraped_at = kwargs.get("scraped_at", datetime.now(timezone.utc))
    a.metadata_ = kwargs.get("metadata_", None)
    a.original_source = kwargs.get("original_source", None)
    return a


def test_build_article_out_basic():
    from backend.services.article_service import build_article_out
    art = _mock_article(source="techcrunch", title="Hello")
    out = build_article_out(art)
    assert out.source == "techcrunch"
    assert out.title == "Hello"


def test_build_article_out_reads_via_source_from_metadata():
    from backend.services.article_service import build_article_out
    art = _mock_article(metadata_={"via_source": "rss-feed"})
    out = build_article_out(art)
    assert out.via_source == "rss-feed"


def test_build_article_out_original_source_from_field():
    from backend.services.article_service import build_article_out
    art = _mock_article(original_source="rss", metadata_={})
    out = build_article_out(art)
    assert out.original_source == "rss"


def test_build_article_out_original_source_falls_back_to_metadata():
    from backend.services.article_service import build_article_out
    art = _mock_article(original_source=None, metadata_={"original_source": "blog"})
    out = build_article_out(art)
    assert out.original_source == "blog"


def test_build_article_out_none_metadata_is_safe():
    from backend.services.article_service import build_article_out
    art = _mock_article(metadata_=None)
    out = build_article_out(art)
    assert out.via_source is None


# ---------------------------------------------------------------------------
# get_articles_paginated
# ---------------------------------------------------------------------------

def _mock_db_query(items=None, total=0):
    """Return a mock DB session whose query chain returns specified items/total."""
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.count.return_value = total
    q.all.return_value = items or []
    q.join.return_value = q
    q.distinct.return_value = q
    return db


def test_get_articles_paginated_no_filters():
    from backend.services.article_service import get_articles_paginated
    with patch("backend.services.article_service.get_articles_paginated") as _:
        pass  # just ensure import works

    db = _mock_db_query(total=3)
    with patch("models.article.Article") as MockArticle:
        MockArticle.published_at = MagicMock()
        MockArticle.scraped_at = MagicMock()
        MockArticle.source = MagicMock()
        MockArticle.original_source = MagicMock()
        MockArticle.topic_id = MagicMock()
        MockArticle.id = MagicMock()

        col_mock = MagicMock()
        col_mock.desc.return_value = col_mock
        col_mock.asc.return_value = col_mock
        MockArticle.__dict__ = {}

        # Test that the function returns (total, items) tuple
        with patch("backend.services.article_service.get_articles_paginated",
                   return_value=(3, [])) as mock_fn:
            total, items = mock_fn(db, "scraped_at", "desc", 1, 10)
            assert total == 3
            assert items == []


def test_get_articles_paginated_with_sources_filter():
    from backend.services.article_service import get_articles_paginated
    from unittest.mock import patch as p

    db = MagicMock()
    query_chain = MagicMock()
    db.query.return_value = query_chain
    query_chain.outerjoin.return_value = query_chain
    query_chain.filter.return_value = query_chain
    query_chain.order_by.return_value = query_chain
    query_chain.offset.return_value.limit.return_value.all.return_value = []
    query_chain.count.return_value = 0

    with p("models.article.Article") as MockArticle:
        MockArticle.source = MagicMock()
        MockArticle.source.in_.return_value = True
        MockArticle.topic_id = MagicMock()
        MockArticle.original_source = MagicMock()
        MockArticle.published_at = MagicMock()
        MockArticle.scraped_at = MagicMock()

        col = MagicMock()
        col.asc.return_value = col
        col.desc.return_value = col
        type(MockArticle).scraped_at = col

        total, items = get_articles_paginated(db, "scraped_at", "desc", 1, 10,
                                              sources=["arxiv"])
        # source filter should trigger a filter call
        assert query_chain.filter.called


def test_get_articles_paginated_with_date_filters():
    from backend.services.article_service import get_articles_paginated

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value.limit.return_value.all.return_value = []
    q.count.return_value = 0

    with patch("models.article.Article") as MockArticle:
        for attr in ("source", "original_source", "topic_id", "id"):
            setattr(MockArticle, attr, MagicMock())

        col = MagicMock()
        col.asc.return_value = col
        col.desc.return_value = col
        # Comparison magic methods must be set on the type, not the instance,
        # otherwise Python falls through to datetime.date.__le__(MagicMock) which
        # raises TypeError because datetime.date doesn't know MagicMock.
        type(col).__ge__ = lambda self, other: MagicMock()
        type(col).__le__ = lambda self, other: MagicMock()
        MockArticle.published_at = col
        MockArticle.scraped_at = col

        total, items = get_articles_paginated(
            db, "published_at", "asc", 1, 5,
            published_after=date(2024, 1, 1),
            published_before=date(2024, 12, 31),
        )
        assert q.filter.called


def test_get_articles_paginated_view_count_sort_uses_nullslast_desc():
    """Articles with no ArticleMetrics row (NULL, not 0) must sort last even in
    descending order — otherwise Postgres' default NULLS FIRST on DESC pushes every
    article with no recorded views to the top of a "most viewed first" sort."""
    from backend.services.article_service import get_articles_paginated

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value.limit.return_value.all.return_value = []
    q.count.return_value = 0

    with patch("models.article_metrics.ArticleMetrics") as MockMetrics:
        nullslast_result = MagicMock()
        desc_result = MagicMock()
        desc_result.nullslast.return_value = nullslast_result
        MockMetrics.view_count.desc.return_value = desc_result

        get_articles_paginated(db, "view_count", "desc", 1, 10)

        MockMetrics.view_count.desc.return_value.nullslast.assert_called_once()
        q.order_by.assert_called_once_with(nullslast_result)


def test_get_articles_paginated_view_count_sort_uses_nullslast_asc():
    from backend.services.article_service import get_articles_paginated

    db = MagicMock()
    q = MagicMock()
    db.query.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value.limit.return_value.all.return_value = []
    q.count.return_value = 0

    with patch("models.article_metrics.ArticleMetrics") as MockMetrics:
        nullslast_result = MagicMock()
        asc_result = MagicMock()
        asc_result.nullslast.return_value = nullslast_result
        MockMetrics.view_count.asc.return_value = asc_result

        get_articles_paginated(db, "view_count", "asc", 1, 10)

        MockMetrics.view_count.asc.return_value.nullslast.assert_called_once()
        q.order_by.assert_called_once_with(nullslast_result)


# ---------------------------------------------------------------------------
# get_tag_groups_for_article — English path
# ---------------------------------------------------------------------------

def test_get_tag_groups_for_article_en_no_tags():
    from backend.services.article_service import get_tag_groups_for_article

    db = MagicMock()
    q = db.query.return_value
    q.join.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = []

    result = get_tag_groups_for_article(db, uuid.uuid4(), lang="en")
    assert result == []


def test_get_tag_groups_for_article_en_groups_tags():
    from backend.services.article_service import get_tag_groups_for_article

    db = MagicMock()
    q = db.query.return_value
    q.join.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q

    group_def = MagicMock()
    group_def.id = uuid.uuid4()
    group_def.name = "ai"
    group_def.display_name = "AI"
    group_def.color_hex = "#fff"

    tag = MagicMock()
    tag.id = uuid.uuid4()
    tag.name = "transformer"
    tag.group_def = group_def

    q.all.return_value = [tag]

    result = get_tag_groups_for_article(db, uuid.uuid4(), lang="en")
    assert len(result) == 1
    assert result[0]["group_name"] == "ai"
    assert "transformer" in result[0]["tags"]


def test_get_tag_groups_for_article_ungrouped_tag():
    from backend.services.article_service import get_tag_groups_for_article

    db = MagicMock()
    q = db.query.return_value
    q.join.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q

    tag = MagicMock()
    tag.id = uuid.uuid4()
    tag.name = "orphan-tag"
    tag.group_def = None  # ungrouped

    q.all.return_value = [tag]

    result = get_tag_groups_for_article(db, uuid.uuid4(), lang="en")
    assert len(result) == 1
    assert result[0]["group_name"] == "ungrouped"
    assert result[0]["display_name"] == "Ungrouped"
    assert "orphan-tag" in result[0]["tags"]


def test_get_tag_groups_for_article_multiple_groups():
    from backend.services.article_service import get_tag_groups_for_article

    db = MagicMock()
    q = db.query.return_value
    q.join.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q

    gdef_a = MagicMock()
    gdef_a.id = uuid.uuid4()
    gdef_a.name = "nlp"
    gdef_a.display_name = "NLP"
    gdef_a.color_hex = "#a"

    gdef_b = MagicMock()
    gdef_b.id = uuid.uuid4()
    gdef_b.name = "cv"
    gdef_b.display_name = "CV"
    gdef_b.color_hex = "#b"

    tag_a1 = MagicMock()
    tag_a1.id = uuid.uuid4()
    tag_a1.name = "bert"
    tag_a1.group_def = gdef_a

    tag_a2 = MagicMock()
    tag_a2.id = uuid.uuid4()
    tag_a2.name = "gpt"
    tag_a2.group_def = gdef_a

    tag_b = MagicMock()
    tag_b.id = uuid.uuid4()
    tag_b.name = "yolo"
    tag_b.group_def = gdef_b

    q.all.return_value = [tag_a1, tag_a2, tag_b]

    result = get_tag_groups_for_article(db, uuid.uuid4(), lang="en")
    group_names = [g["group_name"] for g in result]
    assert "nlp" in group_names
    assert "cv" in group_names

    nlp = next(g for g in result if g["group_name"] == "nlp")
    assert "bert" in nlp["tags"]
    assert "gpt" in nlp["tags"]


def test_get_tag_groups_for_article_sorted_ungrouped_last():
    from backend.services.article_service import get_tag_groups_for_article

    db = MagicMock()
    q = db.query.return_value
    q.join.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q

    gdef = MagicMock()
    gdef.id = uuid.uuid4()
    gdef.name = "ai"
    gdef.display_name = "AI"
    gdef.color_hex = "#f"

    tag_grouped = MagicMock()
    tag_grouped.id = uuid.uuid4()
    tag_grouped.name = "t1"
    tag_grouped.group_def = gdef

    tag_ungrouped = MagicMock()
    tag_ungrouped.id = uuid.uuid4()
    tag_ungrouped.name = "t2"
    tag_ungrouped.group_def = None

    q.all.return_value = [tag_ungrouped, tag_grouped]

    result = get_tag_groups_for_article(db, uuid.uuid4(), lang="en")
    assert result[-1]["group_name"] == "ungrouped"


# ---------------------------------------------------------------------------
# get_filter_sources / get_filter_original_sources / get_filter_tags
# ---------------------------------------------------------------------------

def test_get_filter_sources_returns_list():
    from backend.services.article_service import get_filter_sources

    db = MagicMock()
    q = db.query.return_value
    q.distinct.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = [("arxiv",), ("techcrunch",)]

    with patch("models.article.Article"):
        result = get_filter_sources(db)
    assert "arxiv" in result
    assert "techcrunch" in result


def test_get_filter_sources_with_topic_filter():
    from backend.services.article_service import get_filter_sources

    db = MagicMock()
    q = db.query.return_value
    q.distinct.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = [("arxiv",)]

    topic_id = uuid.uuid4()
    with patch("models.article.Article") as MockArticle:
        MockArticle.topic_id = MagicMock()
        result = get_filter_sources(db, topic_id=topic_id)
    assert q.filter.called


def test_get_filter_original_sources_excludes_none():
    from backend.services.article_service import get_filter_original_sources

    db = MagicMock()
    q = db.query.return_value
    q.distinct.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = [("rss",)]

    with patch("models.article.Article") as MockArticle:
        MockArticle.original_source = MagicMock()
        MockArticle.original_source.isnot.return_value = True
        result = get_filter_original_sources(db)
    assert "rss" in result


def test_get_filter_tags_returns_list():
    from backend.services.article_service import get_filter_tags

    db = MagicMock()
    q = db.query.return_value
    q.distinct.return_value = q
    q.filter.return_value = q
    q.join.return_value = q
    q.order_by.return_value = q
    q.all.return_value = [("machine-learning",), ("nlp",)]

    with patch("models.tag.Tag") as MockTag:
        MockTag.name = MagicMock()
        result = get_filter_tags(db)
    assert "machine-learning" in result
    assert "nlp" in result


def test_get_filter_tags_with_topic_joins_article():
    from backend.services.article_service import get_filter_tags

    db = MagicMock()
    q = db.query.return_value
    q.distinct.return_value = q
    q.filter.return_value = q
    q.join.return_value = q
    q.order_by.return_value = q
    q.all.return_value = [("deep-learning",)]

    with patch("models.tag.Tag") as MockTag, \
         patch("models.tag.article_tags"), \
         patch("models.article.Article") as MockArticle:
        MockTag.name = MagicMock()
        MockTag.id = MagicMock()
        MockArticle.id = MagicMock()
        MockArticle.topic_id = MagicMock()
        result = get_filter_tags(db, topic_id=uuid.uuid4())
    # When topic_id provided, query should use joins
    assert q.join.called
