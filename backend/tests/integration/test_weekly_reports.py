"""Integration tests for GET /weekly-reports and GET /weekly-reports/latest."""
import uuid
from datetime import date, datetime, timezone, timedelta

import pytest

pytestmark = pytest.mark.integration


def _topic(db_session):
    from models.topic import Topic
    topic = Topic(
        id=uuid.uuid4(),
        name=f"topic-{uuid.uuid4().hex[:8]}",
        display_name="AI Weekly",
        is_active=True,
        tag_mode="unsupervised",
    )
    db_session.add(topic)
    db_session.flush()
    return topic


def _weekly_report(topic_id, week_start, status="completed", title="Weekly Report", article_ids=None):
    from models.weekly_report import WeeklyReport
    return WeeklyReport(
        id=uuid.uuid4(),
        topic_id=topic_id,
        week_start_date=week_start,
        title=title,
        summary_text="Summary of the week.",
        cover_image_url=None,
        article_ids=article_ids if article_ids is not None else [],
        article_count=5,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def _article(title="Cited Paper", url=None):
    from models.article import Article
    article_id = uuid.uuid4()
    return Article(
        id=article_id,
        url=url or f"https://example.com/{article_id}",
        url_hash=uuid.uuid4().hex,
        source="rss",
        title=title,
        content="Some content.",
        correlation_id=uuid.uuid4(),
    )


# ─── GET /weekly-reports ─────────────────────────────────────────────────────

def test_list_weekly_reports_empty(db_session, api_client):
    topic = _topic(db_session)
    r = api_client.get(f"/weekly-reports?topic_id={topic.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_weekly_reports_returns_completed_reports(db_session, api_client):
    topic = _topic(db_session)
    w1 = _weekly_report(topic.id, date(2026, 6, 16), title="Report W1")
    w2 = _weekly_report(topic.id, date(2026, 6, 9), title="Report W2")
    db_session.add(w1)
    db_session.add(w2)
    db_session.flush()

    r = api_client.get(f"/weekly-reports?topic_id={topic.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_weekly_reports_pagination(db_session, api_client):
    topic = _topic(db_session)
    for i in range(5):
        db_session.add(_weekly_report(topic.id, date(2026, 1, 6) + timedelta(weeks=i)))
    db_session.flush()

    r = api_client.get(f"/weekly-reports?topic_id={topic.id}&limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5


def test_list_weekly_reports_requires_topic_id(api_client):
    r = api_client.get("/weekly-reports")
    assert r.status_code == 422


def test_list_weekly_reports_is_public(db_session, api_client):
    topic = _topic(db_session)
    r = api_client.get(f"/weekly-reports?topic_id={topic.id}")
    assert r.status_code == 200


# ─── GET /weekly-reports/latest ──────────────────────────────────────────────

def test_get_latest_returns_null_when_no_reports(db_session, api_client):
    topic = _topic(db_session)
    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    assert r.status_code == 200
    assert r.json() is None


def test_get_latest_returns_most_recent_completed_report(db_session, api_client):
    topic = _topic(db_session)
    old = _weekly_report(topic.id, date(2026, 6, 9), title="Old Report")
    new = _weekly_report(topic.id, date(2026, 6, 16), title="New Report")
    db_session.add(old)
    db_session.add(new)
    db_session.flush()

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    assert r.status_code == 200
    data = r.json()
    assert data is not None
    assert data["title"] == "New Report"


def test_get_latest_schema_fields(db_session, api_client):
    topic = _topic(db_session)
    report = _weekly_report(topic.id, date(2026, 6, 16), title="Schema Test")
    db_session.add(report)
    db_session.flush()

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    data = r.json()
    assert "id" in data
    assert "topic_id" in data
    assert "week_start_date" in data
    assert "title" in data
    assert "summary_text" in data
    assert "article_count" in data
    assert "status" in data
    assert "sources" in data


# ─── Citations: sources resolution (2026-07-12, FR-027–FR-028) ──────────────

def test_get_latest_resolves_sources_for_valid_article_ids(db_session, api_client):
    topic = _topic(db_session)
    a1 = _article(title="Paper One")
    a2 = _article(title="Paper Two")
    db_session.add(a1)
    db_session.add(a2)
    db_session.flush()

    report = _weekly_report(
        topic.id,
        date(2026, 6, 16),
        title="Cited Report",
        article_ids=[str(a1.id), str(a2.id)],
    )
    db_session.add(report)
    db_session.flush()

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    assert r.status_code == 200
    data = r.json()
    assert len(data["sources"]) == 2
    assert data["sources"][0]["id"] == str(a1.id)
    assert data["sources"][0]["title"] == "Paper One"
    assert data["sources"][1]["id"] == str(a2.id)


def test_get_latest_returns_empty_sources_for_pre_existing_title_string_article_ids(db_session, api_client):
    """Reports generated before this feature stored article titles (not UUIDs) in article_ids."""
    topic = _topic(db_session)
    report = _weekly_report(
        topic.id,
        date(2026, 6, 16),
        title="Legacy Report",
        article_ids=["Some Old Article Title", "Another Old Title"],
    )
    db_session.add(report)
    db_session.flush()

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["sources"] == []


def test_get_latest_skips_article_id_with_no_matching_article(db_session, api_client):
    """article_ids can reference an article that was later deleted — a well-formed UUID
    with no matching row must be silently skipped, not error."""
    topic = _topic(db_session)
    a1 = _article(title="Still Exists")
    db_session.add(a1)
    db_session.flush()
    missing_id = uuid.uuid4()

    report = _weekly_report(
        topic.id,
        date(2026, 6, 16),
        title="Partially Deleted Report",
        article_ids=[str(a1.id), str(missing_id)],
    )
    db_session.add(report)
    db_session.flush()

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    assert r.status_code == 200
    data = r.json()
    assert len(data["sources"]) == 1
    assert data["sources"][0]["id"] == str(a1.id)


# ─── GET /weekly-reports/weeks ────────────────────────────────────────────────

def test_list_weeks_empty(db_session, api_client):
    topic = _topic(db_session)
    r = api_client.get(f"/weekly-reports/weeks?topic_id={topic.id}")
    assert r.status_code == 200
    assert r.json()["weeks"] == []


def test_list_weeks_returns_completed_report_weeks_desc(db_session, api_client):
    topic = _topic(db_session)
    db_session.add(_weekly_report(topic.id, date(2026, 6, 9)))
    db_session.add(_weekly_report(topic.id, date(2026, 6, 16)))
    db_session.flush()

    r = api_client.get(f"/weekly-reports/weeks?topic_id={topic.id}")
    assert r.status_code == 200
    weeks = r.json()["weeks"]
    assert weeks == ["2026-06-16", "2026-06-09"]


def test_list_weeks_excludes_non_completed_reports(db_session, api_client):
    topic = _topic(db_session)
    db_session.add(_weekly_report(topic.id, date(2026, 6, 9), status="pending"))
    db_session.flush()

    r = api_client.get(f"/weekly-reports/weeks?topic_id={topic.id}")
    assert r.status_code == 200
    assert r.json()["weeks"] == []


def test_list_weeks_requires_topic_id(api_client):
    r = api_client.get("/weekly-reports/weeks")
    assert r.status_code == 422


# ─── GET /weekly-reports/by-week ──────────────────────────────────────────────

def test_get_by_week_returns_null_when_no_match(db_session, api_client):
    topic = _topic(db_session)
    r = api_client.get(f"/weekly-reports/by-week?topic_id={topic.id}&week_start=2026-06-16")
    assert r.status_code == 200
    assert r.json() is None


def test_get_by_week_normalizes_to_monday(db_session, api_client):
    """week_start_date is always a Monday — any date within that week resolves to it."""
    topic = _topic(db_session)
    monday = date(2026, 6, 15)  # Monday
    report = _weekly_report(topic.id, monday, title="Week of June 15")
    db_session.add(report)
    db_session.flush()

    # Thursday of the same week
    r = api_client.get(f"/weekly-reports/by-week?topic_id={topic.id}&week_start=2026-06-18")
    assert r.status_code == 200
    data = r.json()
    assert data is not None
    assert data["title"] == "Week of June 15"
    assert data["week_start_date"] == "2026-06-15"


def test_get_by_week_ignores_non_completed_report(db_session, api_client):
    topic = _topic(db_session)
    db_session.add(_weekly_report(topic.id, date(2026, 6, 15), status="pending"))
    db_session.flush()

    r = api_client.get(f"/weekly-reports/by-week?topic_id={topic.id}&week_start=2026-06-15")
    assert r.status_code == 200
    assert r.json() is None


def test_get_by_week_requires_topic_id_and_week_start(api_client):
    r = api_client.get("/weekly-reports/by-week")
    assert r.status_code == 422


# ─── Translation override (_to_out, FR-030-ish i18n) ─────────────────────────

def _translation(db_session, report_id, language, title, summary_text):
    from models.weekly_report_translation import WeeklyReportTranslation
    t = WeeklyReportTranslation(
        id=uuid.uuid4(),
        weekly_report_id=report_id,
        language=language,
        title=title,
        summary_text=summary_text,
    )
    db_session.add(t)
    db_session.flush()
    return t


def test_get_latest_uses_translation_when_lang_requested(db_session, api_client):
    topic = _topic(db_session)
    report = _weekly_report(topic.id, date(2026, 6, 16), title="English Title")
    db_session.add(report)
    db_session.flush()
    _translation(db_session, report.id, "zh-TW", "中文標題", "中文摘要")

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}&lang=zh-TW")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "中文標題"
    assert data["summary_text"] == "中文摘要"


def test_get_latest_falls_back_to_english_when_translation_missing(db_session, api_client):
    topic = _topic(db_session)
    report = _weekly_report(topic.id, date(2026, 6, 16), title="English Only Title")
    db_session.add(report)
    db_session.flush()

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}&lang=zh-TW")
    assert r.status_code == 200
    assert r.json()["title"] == "English Only Title"


def test_get_latest_default_lang_is_english_no_translation_lookup(db_session, api_client):
    topic = _topic(db_session)
    report = _weekly_report(topic.id, date(2026, 6, 16), title="English Title")
    db_session.add(report)
    db_session.flush()
    _translation(db_session, report.id, "zh-TW", "中文標題", "中文摘要")

    r = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    assert r.status_code == 200
    assert r.json()["title"] == "English Title"


def test_list_weekly_reports_applies_translation_per_item(db_session, api_client):
    topic = _topic(db_session)
    w1 = _weekly_report(topic.id, date(2026, 6, 16), title="Report W1 EN")
    db_session.add(w1)
    db_session.flush()
    _translation(db_session, w1.id, "zh-TW", "報告一", "摘要一")

    r = api_client.get(f"/weekly-reports?topic_id={topic.id}&lang=zh-TW")
    assert r.status_code == 200
    data = r.json()
    assert data["items"][0]["title"] == "報告一"


# ─── Cache-aside reads (020-redis-caching-layer, US1) ────────────────────────

def test_repeated_list_request_is_served_from_cache(db_session, api_client, monkeypatch):
    from backend.routers import weekly_reports as wr_router

    topic = _topic(db_session)
    db_session.add(_weekly_report(topic.id, date(2026, 6, 16)))
    db_session.flush()

    calls = []
    original = wr_router.get_weekly_reports

    def _spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(wr_router, "get_weekly_reports", _spy)

    first = api_client.get(f"/weekly-reports?topic_id={topic.id}")
    second = api_client.get(f"/weekly-reports?topic_id={topic.id}")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"


def test_x_cache_header_is_bypass_when_cache_gateway_unavailable(db_session, api_client):
    """020-redis-caching-layer Post-Ship Addendum (T061): same BYPASS contract as articles.py,
    verified for GET /weekly-reports — each router unpacks CacheResult independently."""
    from backend.main import app
    from backend.cache import get_cache_gateway
    from shared.cache import CacheResult

    topic = _topic(db_session)

    class _BypassGateway:
        def get_or_set(self, namespace, params, ttl_seconds, loader, lang="en"):
            return CacheResult(value=loader(), status="BYPASS")

        def bump_version(self, namespace):
            return 0

    app.dependency_overrides[get_cache_gateway] = lambda: _BypassGateway()
    try:
        response = api_client.get(f"/weekly-reports?topic_id={topic.id}")
    finally:
        app.dependency_overrides.pop(get_cache_gateway, None)

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "BYPASS"


def test_repeated_latest_request_is_served_from_cache(db_session, api_client, monkeypatch):
    from backend.routers import weekly_reports as wr_router

    topic = _topic(db_session)
    db_session.add(_weekly_report(topic.id, date(2026, 6, 16)))
    db_session.flush()

    calls = []
    original = wr_router.get_latest_weekly_report

    def _spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(wr_router, "get_latest_weekly_report", _spy)

    first = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")
    second = api_client.get(f"/weekly-reports/latest?topic_id={topic.id}")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1
