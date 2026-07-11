"""Integration tests for WeeklyReportRepoImpl (spec 014):

  fetch_top_articles() ranking by citation_count -> view_count -> published_at
  save() / find_by_topic_and_week() / get_latest()

Exercises the real SQL joins across articles, article_metrics,
article_metric_values, analyses and analyses_translation — this ranking query
was rewritten in commit 3a52eed for the new metric schema and previously had
no integration coverage (only the use case was unit-tested with a mock repo).
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.infrastructure.persistence.intelligence.weekly_report_repo_impl import WeeklyReportRepoImpl
from src.modules.intelligence.domain.entities.weekly_report import WeeklyReport


def _topic(db_session):
    from models.topic import Topic
    topic = Topic(name=f"wr-topic-{uuid.uuid4().hex[:8]}", display_name="Weekly Report Topic", tag_mode="unsupervised")
    db_session.add(topic)
    db_session.flush()
    return topic


def _article(db_session, topic_id, *, title, scraped_at, published_at=None):
    from models.article import Article
    from src.modules.collection.domain.value_objects import UrlHash

    url = f"https://example.com/{uuid.uuid4()}"
    article = Article(
        url=url,
        url_hash=UrlHash.generate_url_hash(url),
        source="test",
        title=title,
        content="content",
        correlation_id=uuid.uuid4(),
        topic_id=topic_id,
        scraped_at=scraped_at,
        published_at=published_at or scraped_at,
    )
    db_session.add(article)
    db_session.flush()
    return article


def _metrics(db_session, article, *, view_count=0, citation_count=None):
    from models.article_metrics import ArticleMetrics
    from models.article_metric_value import ArticleMetricValue

    db_session.add(ArticleMetrics(article_id=article.id, view_count=view_count))
    if citation_count is not None:
        db_session.add(ArticleMetricValue(
            article_id=article.id, metric_key="citation_count", value=citation_count,
        ))
    db_session.flush()


def _analysis_with_summary(db_session, article, *, summary="Summary text"):
    from models.analysis import Analysis
    from models.analyses_translation import AnalysesTranslation

    analysis = Analysis(article_id=article.id, correlation_id=uuid.uuid4(), model_used="test-model")
    db_session.add(analysis)
    db_session.flush()
    db_session.add(AnalysesTranslation(
        analysis_id=analysis.id, language="en",
        summary=summary, pain_points="pain", insights="insight", innovations="innovation",
    ))
    db_session.flush()


# ---------------------------------------------------------------------------
# fetch_top_articles: ranking
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_fetch_top_articles_ranks_by_citation_count_desc(db_session):
    topic = _topic(db_session)
    week_start = date(2026, 6, 1)
    scraped_at = datetime(2026, 6, 2, tzinfo=timezone.utc)

    low = _article(db_session, topic.id, title="Low citations", scraped_at=scraped_at)
    high = _article(db_session, topic.id, title="High citations", scraped_at=scraped_at)
    _metrics(db_session, low, citation_count=1)
    _metrics(db_session, high, citation_count=100)
    db_session.commit()

    repo = WeeklyReportRepoImpl(session=db_session)
    results = repo.fetch_top_articles(topic.id, week_start)

    assert [a.title for a in results] == ["High citations", "Low citations"]
    assert results[0].citation_count == 100


@pytest.mark.integration
def test_fetch_top_articles_falls_back_to_view_count_when_citations_tie(db_session):
    topic = _topic(db_session)
    week_start = date(2026, 6, 1)
    scraped_at = datetime(2026, 6, 2, tzinfo=timezone.utc)

    few_views = _article(db_session, topic.id, title="Few views", scraped_at=scraped_at)
    many_views = _article(db_session, topic.id, title="Many views", scraped_at=scraped_at)
    _metrics(db_session, few_views, view_count=2)
    _metrics(db_session, many_views, view_count=50)
    db_session.commit()

    repo = WeeklyReportRepoImpl(session=db_session)
    results = repo.fetch_top_articles(topic.id, week_start)

    assert [a.title for a in results] == ["Many views", "Few views"]


@pytest.mark.integration
def test_fetch_top_articles_falls_back_to_published_at_when_no_metrics(db_session):
    topic = _topic(db_session)
    week_start = date(2026, 6, 1)

    older = _article(
        db_session, topic.id, title="Older",
        scraped_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
    )
    newer = _article(
        db_session, topic.id, title="Newer",
        scraped_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        published_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
    )
    db_session.commit()

    repo = WeeklyReportRepoImpl(session=db_session)
    results = repo.fetch_top_articles(topic.id, week_start)

    assert [a.title for a in results] == ["Newer", "Older"]
    assert all(a.citation_count is None for a in results)
    assert all(a.view_count == 0 for a in results)


@pytest.mark.integration
def test_fetch_top_articles_excludes_articles_outside_week_range(db_session):
    topic = _topic(db_session)
    week_start = date(2026, 6, 1)

    in_range = _article(db_session, topic.id, title="In range", scraped_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    before_range = _article(db_session, topic.id, title="Before range", scraped_at=datetime(2026, 5, 30, tzinfo=timezone.utc))
    after_range = _article(db_session, topic.id, title="After range", scraped_at=datetime(2026, 6, 9, tzinfo=timezone.utc))
    db_session.commit()

    repo = WeeklyReportRepoImpl(session=db_session)
    results = repo.fetch_top_articles(topic.id, week_start)

    titles = {a.title for a in results}
    assert titles == {"In range"}


@pytest.mark.integration
def test_fetch_top_articles_includes_analysis_summary_fields(db_session):
    topic = _topic(db_session)
    week_start = date(2026, 6, 1)
    article = _article(db_session, topic.id, title="Analyzed", scraped_at=datetime(2026, 6, 2, tzinfo=timezone.utc))
    _analysis_with_summary(db_session, article, summary="A great summary")
    db_session.commit()

    repo = WeeklyReportRepoImpl(session=db_session)
    results = repo.fetch_top_articles(topic.id, week_start)

    assert len(results) == 1
    assert results[0].summary == "A great summary"
    assert results[0].pain_points == "pain"


# ---------------------------------------------------------------------------
# save() / find_by_topic_and_week() / get_latest()
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_save_then_find_by_topic_and_week_round_trips(db_session):
    topic = _topic(db_session)
    week_start = date(2026, 6, 1)
    repo = WeeklyReportRepoImpl(session=db_session)

    report = WeeklyReport(
        id=uuid.uuid4(), topic_id=topic.id, week_start_date=week_start,
        title="Week 1", summary_text="Summary", cover_image_url=None,
        article_ids=["a", "b"], article_count=2, status="completed",
    )
    saved = repo.save(report)
    assert saved.id is not None

    found = repo.find_by_topic_and_week(topic.id, week_start)
    assert found is not None
    assert found.title == "Week 1"
    assert found.article_count == 2


@pytest.mark.integration
def test_save_upserts_existing_report_for_same_topic_and_week(db_session):
    topic = _topic(db_session)
    week_start = date(2026, 6, 1)
    repo = WeeklyReportRepoImpl(session=db_session)

    first = WeeklyReport(
        id=uuid.uuid4(), topic_id=topic.id, week_start_date=week_start,
        title="Original", summary_text="First", cover_image_url=None,
        article_ids=[], article_count=0, status="completed",
    )
    saved_first = repo.save(first)

    second = WeeklyReport(
        id=uuid.uuid4(), topic_id=topic.id, week_start_date=week_start,
        title="Updated", summary_text="Second", cover_image_url=None,
        article_ids=["x"], article_count=1, status="completed",
    )
    saved_second = repo.save(second)

    assert saved_second.id == saved_first.id  # same underlying row, re-pointed id

    found = repo.find_by_topic_and_week(topic.id, week_start)
    assert found.title == "Updated"
    assert found.article_count == 1


@pytest.mark.integration
def test_get_latest_returns_most_recent_completed_report(db_session):
    topic = _topic(db_session)
    repo = WeeklyReportRepoImpl(session=db_session)

    repo.save(WeeklyReport(
        id=uuid.uuid4(), topic_id=topic.id, week_start_date=date(2026, 5, 25),
        title="Old week", summary_text="", cover_image_url=None,
        article_ids=[], article_count=0, status="completed",
    ))
    repo.save(WeeklyReport(
        id=uuid.uuid4(), topic_id=topic.id, week_start_date=date(2026, 6, 1),
        title="Newest week", summary_text="", cover_image_url=None,
        article_ids=[], article_count=0, status="completed",
    ))

    latest = repo.get_latest(topic.id)
    assert latest is not None
    assert latest.title == "Newest week"


@pytest.mark.integration
def test_get_latest_ignores_non_completed_reports(db_session):
    topic = _topic(db_session)
    repo = WeeklyReportRepoImpl(session=db_session)

    repo.save(WeeklyReport(
        id=uuid.uuid4(), topic_id=topic.id, week_start_date=date(2026, 6, 1),
        title="Pending week", summary_text="", cover_image_url=None,
        article_ids=[], article_count=0, status="pending",
    ))

    assert repo.get_latest(topic.id) is None
