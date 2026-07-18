"""Integration tests for /metric-definitions (public) and /admin/metric-definitions (admin).

2026-07-12, User Story 8 & 9 (FR-036-FR-042): generalized metric display + admin enable/disable.
2026-07-12 (later same day): metric_definitions split into metric_definitions (metric_key-level,
admin-editable enabled/icon_name) + metric_providers (maintainer-only extraction config) — see
alembic 23 revision notes for why.
"""
import time
import uuid

import pytest
from jose import jwt

pytestmark = pytest.mark.integration


def admin_token() -> str:
    payload = {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, "test-secret", algorithm="HS256")


_ADMIN_HDR = {"Authorization": f"Bearer {admin_token()}"}


def _definition(db_session, *, metric_key="citation_count", enabled=True,
                label_i18n_key="metrics.citation_count", icon_name="quote"):
    from models.metric_definition import MetricDefinition
    obj = MetricDefinition(
        id=uuid.uuid4(),
        metric_key=metric_key,
        label_i18n_key=label_i18n_key,
        format_hint="integer",
        unit=None,
        icon_name=icon_name,
        enabled=enabled,
    )
    db_session.add(obj)
    db_session.flush()
    return obj


def _provider(db_session, definition, *, provider_name="openalex", priority=1):
    from models.metric_provider import MetricProvider
    obj = MetricProvider(
        id=uuid.uuid4(),
        metric_definition_id=definition.id,
        provider_name=provider_name,
        priority=priority,
        extractor_type="json_path",
        extractor_spec={"path": "some.path"},
    )
    db_session.add(obj)
    db_session.flush()
    return obj


# ─── GET /metric-definitions (public) ────────────────────────────────────────

def test_public_list_requires_no_auth(db_session, api_client):
    d = _definition(db_session)
    _provider(db_session, d)
    r = api_client.get("/metric-definitions")
    assert r.status_code == 200


def test_public_list_returns_only_enabled_rows(db_session, api_client):
    enabled = _definition(db_session, metric_key="citation_count", enabled=True)
    _provider(db_session, enabled)
    disabled = _definition(db_session, metric_key="impact_factor", enabled=False)
    _provider(db_session, disabled, provider_name="scopus")

    r = api_client.get("/metric-definitions")
    keys = [item["metric_key"] for item in r.json()]
    assert "citation_count" in keys
    assert "impact_factor" not in keys


def test_public_list_has_one_entry_per_metric_key_even_with_multiple_providers(db_session, api_client):
    """A metric_key with several providers (e.g. citation_count via openalex + semantic_scholar)
    is still exactly one metric_definitions row now — no dedup logic needed, the DB itself
    enforces UNIQUE(metric_key)."""
    d = _definition(db_session, metric_key="citation_count")
    _provider(db_session, d, provider_name="openalex", priority=1)
    _provider(db_session, d, provider_name="semantic_scholar", priority=2)
    _provider(db_session, d, provider_name="semantic_scholar_arxiv", priority=3)

    r = api_client.get("/metric-definitions")
    keys = [item["metric_key"] for item in r.json()]
    assert keys.count("citation_count") == 1


def test_public_list_does_not_expose_provider_or_extraction_internals(db_session, api_client):
    d = _definition(db_session)
    _provider(db_session, d)
    r = api_client.get("/metric-definitions")
    item = r.json()[0]
    assert "provider_name" not in item
    assert "extractor_spec" not in item
    assert "extractor_type" not in item
    assert "priority" not in item
    assert "enabled" not in item  # public shape has no need to expose this either
    assert item["icon_name"] == "quote"
    assert item["label_i18n_key"] == "metrics.citation_count"


# ─── GET /admin/metric-definitions ───────────────────────────────────────────

def test_admin_list_requires_admin(api_client):
    r = api_client.get("/admin/metric-definitions")
    assert r.status_code in (401, 403)


def test_admin_list_includes_disabled_rows(db_session, api_client):
    enabled = _definition(db_session, metric_key="citation_count", enabled=True)
    _provider(db_session, enabled)
    disabled = _definition(db_session, metric_key="impact_factor", enabled=False)
    _provider(db_session, disabled, provider_name="scopus")

    r = api_client.get("/admin/metric-definitions", headers=_ADMIN_HDR)
    assert r.status_code == 200
    keys = [item["metric_key"] for item in r.json()]
    assert "citation_count" in keys
    assert "impact_factor" in keys


def test_admin_list_does_not_expose_provider_or_priority(db_session, api_client):
    """Admin sees one row per metric_key, never provider/priority plumbing (2026-07-12 discussion)."""
    d = _definition(db_session)
    _provider(db_session, d, provider_name="openalex", priority=1)
    _provider(db_session, d, provider_name="semantic_scholar", priority=2)

    r = api_client.get("/admin/metric-definitions", headers=_ADMIN_HDR)
    assert r.status_code == 200
    items = [item for item in r.json() if item["metric_key"] == "citation_count"]
    assert len(items) == 1  # not one row per provider
    assert "provider_name" not in items[0]
    assert "priority" not in items[0]


# ─── PATCH /admin/metric-definitions/{id} ────────────────────────────────────

def test_patch_requires_admin(db_session, api_client):
    obj = _definition(db_session)
    r = api_client.patch(f"/admin/metric-definitions/{obj.id}", json={"enabled": False})
    assert r.status_code in (401, 403)


def test_patch_toggles_enabled(db_session, api_client):
    obj = _definition(db_session, enabled=True)
    _provider(db_session, obj)
    r = api_client.patch(f"/admin/metric-definitions/{obj.id}", json={"enabled": False}, headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    # Disabled metric no longer appears in the public list
    public = api_client.get("/metric-definitions")
    assert obj.metric_key not in [item["metric_key"] for item in public.json()]


def test_patch_updates_icon_name_when_valid(db_session, api_client):
    obj = _definition(db_session, icon_name="quote")
    r = api_client.patch(f"/admin/metric-definitions/{obj.id}", json={"icon_name": "trophy"}, headers=_ADMIN_HDR)
    assert r.status_code == 200
    assert r.json()["icon_name"] == "trophy"


def test_patch_rejects_icon_name_outside_whitelist(db_session, api_client):
    obj = _definition(db_session)
    r = api_client.patch(f"/admin/metric-definitions/{obj.id}", json={"icon_name": "not-a-real-icon"}, headers=_ADMIN_HDR)
    assert r.status_code == 422


def test_patch_ignores_fields_other_than_enabled_and_icon_name(db_session, api_client):
    obj = _definition(db_session, enabled=True)
    _provider(db_session, obj)
    r = api_client.patch(
        f"/admin/metric-definitions/{obj.id}",
        json={"enabled": False, "label_i18n_key": "hacked"},
        headers=_ADMIN_HDR,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["label_i18n_key"] == "metrics.citation_count"  # unchanged


def test_patch_unknown_id_returns_404(api_client):
    r = api_client.patch(f"/admin/metric-definitions/{uuid.uuid4()}", json={"enabled": False}, headers=_ADMIN_HDR)
    assert r.status_code == 404


# ─── GET /articles sort by an enabled metric_key (US8, generalized sort) ────

def test_articles_sort_by_non_citation_metric_key(db_session, api_client):
    from models.article import Article
    from models.article_metric_value import ArticleMetricValue

    def _article(title):
        return Article(
            url=f"https://example.com/{uuid.uuid4()}", url_hash=uuid.uuid4().hex, source="test",
            title=title, content="body", correlation_id=uuid.uuid4(),
        )

    low = _article("Low impact")
    high = _article("High impact")
    db_session.add(low)
    db_session.add(high)
    db_session.flush()
    db_session.add(ArticleMetricValue(article_id=low.id, metric_key="impact_factor", value=1.2))
    db_session.add(ArticleMetricValue(article_id=high.id, metric_key="impact_factor", value=9.8))
    db_session.flush()

    r = api_client.get("/articles?sort=impact_factor&order=desc")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["title"] == "High impact"
    assert items[-1]["title"] == "Low impact"
