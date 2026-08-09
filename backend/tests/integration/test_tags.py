"""
Integration tests for /tag-groups and /tags endpoints.

Unit tests mock all DB calls. These tests exercise real SQL:
  - tag group CRUD and auth guards
  - tag rename, ungroup, delete
  - batch-move tags
  - tag group reorder and merge
  - tag normalization suggestion list/approve/reject
"""
import time
import uuid

import pytest
from jose import jwt

# Ensure these models are registered with Base.metadata before db_engine creates tables
from models.tag_normalization_suggestion import TagNormalizationSuggestion  # noqa: F401

pytestmark = pytest.mark.integration

_JWT_SECRET = "test-secret"


def admin_token() -> str:
    payload = {"sub": str(uuid.uuid4()), "role": "admin", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}


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


def _group(db_session, topic, name=None, display_name=None, sort_order=1):
    from models.tag_group import TagGroupDefinition
    name = name or f"grp-{uuid.uuid4().hex[:6]}"
    g = TagGroupDefinition(
        id=uuid.uuid4(),
        name=name,
        display_name=display_name or name.title(),
        color_hex="#3b82f6",
        sort_order=sort_order,
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


def _article(db_session, topic=None):
    from models.article import Article
    a = Article(
        id=uuid.uuid4(),
        url=f"https://example.com/{uuid.uuid4().hex}",
        url_hash=uuid.uuid4().hex,
        source="test",
        title="Test Article",
        content="body",
        correlation_id=uuid.uuid4(),
        topic_id=topic.id if topic else None,
    )
    db_session.add(a)
    db_session.flush()
    return a


def _link(db_session, article, tag):
    from models.tag import article_tags
    db_session.execute(article_tags.insert().values(article_id=article.id, tag_id=tag.id))
    db_session.flush()


def _suggestion(db_session, new_tag, existing_tag, article=None):
    sug = TagNormalizationSuggestion(
        id=uuid.uuid4(),
        new_tag_id=new_tag.id,
        existing_tag_id=existing_tag.id,
        similarity_score=0.95,
        status="pending",
        article_id=article.id if article else None,
    )
    db_session.add(sug)
    db_session.flush()
    return sug


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_create_tag_group_requires_admin(api_client):
    r = api_client.post("/tag-groups", json={"name": "x", "display_name": "X"})
    assert r.status_code in (401, 403)


def test_update_tag_group_requires_admin(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic)
    r = api_client.put(f"/tag-groups/{grp.id}", json={"display_name": "New"})
    assert r.status_code in (401, 403)


def test_delete_tag_group_requires_admin(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic)
    r = api_client.delete(f"/tag-groups/{grp.id}")
    assert r.status_code in (401, 403)


def test_rename_tag_requires_admin(api_client, db_session):
    tag = _tag(db_session)
    r = api_client.put(f"/tags/{tag.id}", json={"name": "new-name"})
    assert r.status_code in (401, 403)


def test_delete_tag_requires_admin(api_client, db_session):
    tag = _tag(db_session)
    r = api_client.delete(f"/tags/{tag.id}")
    assert r.status_code in (401, 403)


def test_batch_move_requires_admin(api_client):
    r = api_client.post("/tags/batch-move", json=[])
    assert r.status_code in (401, 403)


def test_list_suggestions_requires_admin(api_client):
    r = api_client.get("/tag-normalization-suggestions")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List tag groups
# ---------------------------------------------------------------------------

def test_list_tag_groups_empty(api_client):
    r = api_client.get("/tag-groups")
    assert r.status_code == 200
    assert r.json() == []


def test_list_tag_groups_returns_groups_for_topic(api_client, db_session):
    topic = _topic(db_session)
    _group(db_session, topic, name="vision", display_name="Vision")
    _group(db_session, topic, name="nlp", display_name="NLP")

    r = api_client.get(f"/tag-groups?topic_id={topic.id}")
    assert r.status_code == 200
    names = {g["name"] for g in r.json()}
    assert "vision" in names
    assert "nlp" in names


def test_list_tag_groups_filtered_by_topic(api_client, db_session):
    topic_a = _topic(db_session)
    topic_b = _topic(db_session)
    _group(db_session, topic_a, name="only-in-a")
    _group(db_session, topic_b, name="only-in-b")

    r = api_client.get(f"/tag-groups?topic_id={topic_a.id}")
    names = [g["name"] for g in r.json()]
    assert "only-in-a" in names
    assert "only-in-b" not in names


def test_list_tag_groups_includes_ungrouped_when_topic_given(api_client, db_session):
    topic = _topic(db_session)
    art = _article(db_session, topic)
    orphan = _tag(db_session, name="orphan-tag")
    _link(db_session, art, orphan)

    r = api_client.get(f"/tag-groups?topic_id={topic.id}")
    groups = r.json()
    ungrouped = next((g for g in groups if g["name"] == "ungrouped"), None)
    assert ungrouped is not None
    tag_names = [t["name"] for t in ungrouped["tags"]]
    assert "orphan-tag" in tag_names


def test_list_tag_groups_response_shape(api_client, db_session):
    topic = _topic(db_session)
    _group(db_session, topic, name="shape-test")

    r = api_client.get(f"/tag-groups?topic_id={topic.id}")
    grp = r.json()[0]
    assert "id" in grp
    assert "name" in grp
    assert "display_name" in grp
    assert "tags" in grp


# ---------------------------------------------------------------------------
# Get single tag group
# ---------------------------------------------------------------------------

def test_get_tag_group_by_id(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic, name="specific-group")

    r = api_client.get(f"/tag-groups/{grp.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "specific-group"
    assert r.json()["id"] == str(grp.id)


def test_get_tag_group_not_found(api_client):
    r = api_client.get(f"/tag-groups/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Create tag group
# ---------------------------------------------------------------------------

def test_create_tag_group_returns_201(api_client, db_session):
    from unittest.mock import patch
    topic = _topic(db_session)
    # embed_text may call real API if GEMINI_API_KEY is set; mock to avoid dimension mismatch
    with patch("backend.routers.tags.embed_text", return_value=None):
        r = api_client.post(
            "/tag-groups",
            json={"name": "new_grp", "display_name": "New Grp", "topic_id": str(topic.id)},
            headers=_ADMIN_HDR,
        )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "new_grp"
    assert "id" in data


def test_create_tag_group_appears_in_list(api_client, db_session):
    from unittest.mock import patch
    topic = _topic(db_session)
    with patch("backend.routers.tags.embed_text", return_value=None):
        api_client.post(
            "/tag-groups",
            json={"name": "listable", "display_name": "Listable", "topic_id": str(topic.id)},
            headers=_ADMIN_HDR,
        )
    names = [g["name"] for g in api_client.get(f"/tag-groups?topic_id={topic.id}").json()]
    assert "listable" in names


def test_create_tag_group_with_color(api_client, db_session):
    from unittest.mock import patch
    topic = _topic(db_session)
    with patch("backend.routers.tags.embed_text", return_value=None):
        r = api_client.post(
            "/tag-groups",
            json={"name": "colorful", "display_name": "Colorful", "color_hex": "#ff0000",
                  "topic_id": str(topic.id)},
            headers=_ADMIN_HDR,
        )
    assert r.status_code == 201
    assert r.json()["color_hex"] == "#ff0000"


# ---------------------------------------------------------------------------
# Update tag group
# ---------------------------------------------------------------------------

def test_update_tag_group_display_name(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic)

    r = api_client.put(
        f"/tag-groups/{grp.id}",
        json={"display_name": "Updated Display"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Updated Display"


def test_update_tag_group_not_found(api_client):
    r = api_client.put(
        f"/tag-groups/{uuid.uuid4()}",
        json={"display_name": "Ghost"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 404


def test_update_tag_group_duplicate_name_returns_409(api_client, db_session):
    topic = _topic(db_session)
    # Use already-slugified names (underscores) so schema normalization produces the same value
    _group(db_session, topic, name="taken_name")
    grp2 = _group(db_session, topic, name="to_rename")

    r = api_client.put(
        f"/tag-groups/{grp2.id}",
        json={"name": "taken_name"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Delete tag group
# ---------------------------------------------------------------------------

def test_delete_tag_group_returns_204(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic)

    r = api_client.delete(f"/tag-groups/{grp.id}", headers=_ADMIN_HDR)
    assert r.status_code == 204


def test_delete_tag_group_no_longer_returned(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic)

    api_client.delete(f"/tag-groups/{grp.id}", headers=_ADMIN_HDR)

    r = api_client.get(f"/tag-groups/{grp.id}")
    assert r.status_code == 404


def test_delete_tag_group_not_found(api_client):
    r = api_client.delete(f"/tag-groups/{uuid.uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Rename tag
# ---------------------------------------------------------------------------

def test_rename_tag_updates_name(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic)
    tag = _tag(db_session, name="old-name", group=grp)

    r = api_client.put(f"/tags/{tag.id}", json={"name": "new-name"}, headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["name"] == "new-name"


def test_rename_tag_not_found(api_client):
    r = api_client.put(f"/tags/{uuid.uuid4()}", json={"name": "x"}, headers=_ADMIN_HDR)
    assert r.status_code == 404


def test_ungroup_tag_removes_group_assignment(api_client, db_session):
    topic = _topic(db_session)
    grp = _group(db_session, topic)
    tag = _tag(db_session, name="grouped-tag", group=grp)

    r = api_client.put(f"/tags/{tag.id}", json={"ungroup": True}, headers=_ADMIN_HDR)
    assert r.status_code == 200

    db_session.refresh(tag)
    assert tag.tag_group_id is None


def test_move_tag_to_different_group(api_client, db_session):
    topic = _topic(db_session)
    grp_a = _group(db_session, topic, name="src-group")
    grp_b = _group(db_session, topic, name="dst-group")
    tag = _tag(db_session, name="movable", group=grp_a)

    r = api_client.put(
        f"/tags/{tag.id}",
        json={"tag_group_id": str(grp_b.id)},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200

    db_session.refresh(tag)
    assert tag.tag_group_id == grp_b.id


# ---------------------------------------------------------------------------
# Delete tag
# ---------------------------------------------------------------------------

def test_delete_tag_returns_204(api_client, db_session):
    tag = _tag(db_session)
    r = api_client.delete(f"/tags/{tag.id}", headers=_ADMIN_HDR)
    assert r.status_code == 204


def test_delete_tag_not_found(api_client):
    r = api_client.delete(f"/tags/{uuid.uuid4()}", headers=_ADMIN_HDR)
    assert r.status_code == 404


def test_delete_tag_also_removes_article_links(api_client, db_session):
    from models.tag import article_tags
    from sqlalchemy import select

    art = _article(db_session)
    tag = _tag(db_session)
    _link(db_session, art, tag)

    api_client.delete(f"/tags/{tag.id}", headers=_ADMIN_HDR)

    remaining = db_session.execute(
        select(article_tags).where(article_tags.c.tag_id == tag.id)
    ).fetchall()
    assert remaining == []


# ---------------------------------------------------------------------------
# Batch move tags
# ---------------------------------------------------------------------------

def test_batch_move_tags_all_succeed(api_client, db_session):
    topic = _topic(db_session)
    src = _group(db_session, topic, name="src")
    dst = _group(db_session, topic, name="dst")
    t1 = _tag(db_session, name="t1", group=src)
    t2 = _tag(db_session, name="t2", group=src)

    r = api_client.post(
        "/tags/batch-move",
        json=[
            {"tag_id": str(t1.id), "tag_group_id": str(dst.id)},
            {"tag_id": str(t2.id), "tag_group_id": str(dst.id)},
        ],
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["succeeded"]) == 2
    assert data["failed"] == []


def test_batch_move_unknown_tag_goes_to_failed(api_client):
    r = api_client.post(
        "/tags/batch-move",
        json=[{"tag_id": str(uuid.uuid4()), "tag_group_id": str(uuid.uuid4())}],
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert len(r.json()["failed"]) == 1


def test_batch_move_empty_payload(api_client):
    r = api_client.post("/tags/batch-move", json=[], headers=_ADMIN_HDR)
    assert r.status_code == 200
    data = r.json()
    assert data["succeeded"] == []
    assert data["failed"] == []


# ---------------------------------------------------------------------------
# Reorder tag groups
# ---------------------------------------------------------------------------

def test_reorder_tag_groups_returns_204(api_client, db_session):
    topic = _topic(db_session)
    grp_a = _group(db_session, topic, name="alpha", sort_order=1)
    grp_b = _group(db_session, topic, name="beta", sort_order=2)

    r = api_client.post(
        "/tag-groups/reorder",
        json=[{"id": str(grp_a.id), "sort_order": 2},
              {"id": str(grp_b.id), "sort_order": 1}],
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 204


def test_reorder_tag_groups_persists_sort_order(api_client, db_session):
    from models.tag_group import TagGroupDefinition

    topic = _topic(db_session)
    grp_a = _group(db_session, topic, name="first", sort_order=1)
    grp_b = _group(db_session, topic, name="second", sort_order=2)

    api_client.post(
        "/tag-groups/reorder",
        json=[{"id": str(grp_a.id), "sort_order": 99},
              {"id": str(grp_b.id), "sort_order": 1}],
        headers=_ADMIN_HDR,
    )

    db_session.refresh(grp_a)
    assert grp_a.sort_order == 99


# ---------------------------------------------------------------------------
# Merge tag groups
# ---------------------------------------------------------------------------

def test_merge_creates_new_result_group(api_client, db_session):
    topic = _topic(db_session)
    # Use slug names (underscores) — schema validator converts hyphens to underscores
    grp_a = _group(db_session, topic, name="merge_a")
    grp_b = _group(db_session, topic, name="merge_b")
    tag_a = _tag(db_session, name="tag_from_a", group=grp_a)
    tag_b = _tag(db_session, name="tag_from_b", group=grp_b)
    # tag_outs_for_group uses INNER JOIN on article_tags, so tags need article links to appear
    art = _article(db_session, topic)
    _link(db_session, art, tag_a)
    _link(db_session, art, tag_b)

    r = api_client.post(
        "/tag-groups/merge",
        json={
            "group_a_id": str(grp_a.id),
            "group_b_id": str(grp_b.id),
            "result_name": "merged_result",
            "result_display_name": "Merged Result",
            "result_color_hex": "#ff00ff",
            "result_description": None,
        },
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "merged_result"
    tag_names = [t["name"] for t in data["tags"]]
    assert "tag_from_a" in tag_names
    assert "tag_from_b" in tag_names


def test_merge_into_group_a_keeps_a(api_client, db_session):
    topic = _topic(db_session)
    # result_name must exactly match group_a.name in DB for the service to reuse it
    grp_a = _group(db_session, topic, name="keep_a")
    grp_b = _group(db_session, topic, name="absorb_b")
    _tag(db_session, name="tag_a", group=grp_a)
    _tag(db_session, name="tag_b", group=grp_b)

    r = api_client.post(
        "/tag-groups/merge",
        json={
            "group_a_id": str(grp_a.id),
            "group_b_id": str(grp_b.id),
            "result_name": "keep_a",
            "result_display_name": "Keep A",
            "result_color_hex": None,
            "result_description": None,
        },
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "keep_a"


def test_merge_nonexistent_group_returns_404(api_client):
    r = api_client.post(
        "/tag-groups/merge",
        json={
            "group_a_id": str(uuid.uuid4()),
            "group_b_id": str(uuid.uuid4()),
            "result_name": "result",
            "result_display_name": "Result",
            "result_color_hex": None,
            "result_description": None,
        },
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 404


def test_merge_deduplicates_tags_with_same_name(api_client, db_session):
    topic = _topic(db_session)
    grp_a = _group(db_session, topic, name="dedup_a")
    grp_b = _group(db_session, topic, name="dedup_b")
    tag_a = _tag(db_session, name="shared_tag", group=grp_a)
    tag_b = _tag(db_session, name="shared_tag", group=grp_b)
    # Need article links so tag_outs_for_group (INNER JOIN) can return the tag
    art = _article(db_session, topic)
    _link(db_session, art, tag_a)
    _link(db_session, art, tag_b)

    r = api_client.post(
        "/tag-groups/merge",
        json={
            "group_a_id": str(grp_a.id),
            "group_b_id": str(grp_b.id),
            "result_name": "dedup_result",
            "result_display_name": "Dedup Result",
            "result_color_hex": None,
            "result_description": None,
        },
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    tag_names = [t["name"] for t in r.json()["tags"]]
    assert tag_names.count("shared_tag") == 1


# ---------------------------------------------------------------------------
# Tag normalization suggestions
# ---------------------------------------------------------------------------

def test_list_suggestions_empty(api_client):
    r = api_client.get("/tag-normalization-suggestions", headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json() == []


def test_approve_suggestion_not_found(api_client):
    r = api_client.post(
        f"/tag-normalization-suggestions/{uuid.uuid4()}/approve",
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 404


def test_reject_suggestion_not_found(api_client):
    r = api_client.post(
        f"/tag-normalization-suggestions/{uuid.uuid4()}/reject",
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 404


def test_reject_suggestion_marks_as_rejected(api_client, db_session):
    tag_new = _tag(db_session, name="new-variant")
    tag_existing = _tag(db_session, name="existing-canonical")
    sug = _suggestion(db_session, tag_new, tag_existing)

    r = api_client.post(
        f"/tag-normalization-suggestions/{sug.id}/reject",
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    db_session.refresh(sug)
    assert sug.status == "rejected"
    assert sug.resolved_at is not None


def test_approve_suggestion_merges_tags(api_client, db_session):
    art = _article(db_session)
    tag_new = _tag(db_session, name="new-form")
    tag_existing = _tag(db_session, name="canonical-form")
    _link(db_session, art, tag_new)
    sug = _suggestion(db_session, tag_new, tag_existing, article=art)

    r = api_client.post(
        f"/tag-normalization-suggestions/{sug.id}/approve",
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Cache write-through (020-redis-caching-layer, US2)
# ---------------------------------------------------------------------------

def _spy_bump_version(monkeypatch):
    calls = []
    from backend.cache import cache_gateway

    original = cache_gateway.bump_version

    def _spy(namespace):
        calls.append(namespace)
        return original(namespace)

    monkeypatch.setattr(cache_gateway, "bump_version", _spy)
    return calls


def test_rename_tag_bumps_article_scoped_caches(api_client, db_session, monkeypatch):
    tag = _tag(db_session, name="rename-me")
    calls = _spy_bump_version(monkeypatch)
    api_client.put(f"/tags/{tag.id}", json={"name": "renamed"}, headers=_ADMIN_HDR)
    assert set(calls) == {"articles", "graph", "tag_groups"}


def test_delete_tag_bumps_article_scoped_caches(api_client, db_session, monkeypatch):
    tag = _tag(db_session, name="delete-me")
    calls = _spy_bump_version(monkeypatch)
    api_client.delete(f"/tags/{tag.id}", headers=_ADMIN_HDR)
    assert set(calls) == {"articles", "graph", "tag_groups"}


def test_repeated_tag_groups_request_is_served_from_cache(api_client, db_session, monkeypatch):
    from backend.routers import tags as tags_router

    topic = _topic(db_session)
    _group(db_session, topic, name="cache-hit-group")

    calls = []
    original = tags_router.tag_outs_for_group

    def _spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(tags_router, "tag_outs_for_group", _spy)

    first = api_client.get(f"/tag-groups?topic_id={topic.id}")
    second = api_client.get(f"/tag-groups?topic_id={topic.id}")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"


def test_x_cache_header_is_bypass_when_cache_gateway_unavailable(api_client):
    """020-redis-caching-layer Post-Ship Addendum (T061): same BYPASS contract as articles.py,
    verified for GET /tag-groups — each router unpacks CacheResult independently."""
    from backend.main import app
    from backend.cache import get_cache_gateway
    from shared.cache import CacheResult

    class _BypassGateway:
        def get_or_set(self, namespace, params, ttl_seconds, loader, lang="en"):
            return CacheResult(value=loader(), status="BYPASS")

        def bump_version(self, namespace):
            return 0

    app.dependency_overrides[get_cache_gateway] = lambda: _BypassGateway()
    try:
        response = api_client.get("/tag-groups")
    finally:
        app.dependency_overrides.pop(get_cache_gateway, None)

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"


def test_tag_group_rename_reflected_on_next_read(api_client, db_session):
    """End-to-end: cache tag-groups, rename a group, confirm the very next read reflects it."""
    topic = _topic(db_session)
    grp = _group(db_session, topic, name="before-rename", display_name="Before Rename")

    first = api_client.get(f"/tag-groups?topic_id={topic.id}")
    names = [g["display_name"] for g in first.json()]
    assert "Before Rename" in names

    api_client.put(
        f"/tag-groups/{grp.id}",
        json={"display_name": "After Rename"},
        headers=_ADMIN_HDR,
    )

    second = api_client.get(f"/tag-groups?topic_id={topic.id}")
    names_after = [g["display_name"] for g in second.json()]
    assert "After Rename" in names_after
    assert "Before Rename" not in names_after
