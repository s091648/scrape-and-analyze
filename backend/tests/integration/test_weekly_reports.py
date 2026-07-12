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
