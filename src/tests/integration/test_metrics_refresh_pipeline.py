"""Integration tests for the recurring metric refresh pipeline (spec 011 / 014):

  MetricExtractor -> ResilientMetricsService -> SqlAlchemyArticleMetricsRepository.upsert()

and SqlAlchemyArticleMetricsRepository.find_stale(), the stale-articles
discovery query used by src/entrypoints/cli/refresh_metrics.py.

Real PostgreSQL, fake (non-HTTP) extractors — mirrors the pattern used for the
LLM provider chain in test_process_article.py.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.infrastructure.collection.metrics.resilient_metrics_service import (
    MetricHandler,
    ResilientMetricsService,
)
from src.modules.collection.domain.services import MetricExtractor


class _FakeExtractor(MetricExtractor):
    """Returns a fixed value, or raises/returns None to simulate provider failure."""

    def __init__(self, value=None, raises=False):
        self._value = value
        self._raises = raises

    def fetch(self, article_identifiers):
        if self._raises:
            raise RuntimeError("simulated fetch failure")
        return {"value": self._value} if self._value is not None else None

    def extract(self, raw_response, extractor_spec):
        return raw_response.get("value")


def _make_article(db_session, *, doi=None, arxiv_id=None, title="Metrics Article"):
    from models.article import Article
    from src.modules.collection.domain.value_objects import UrlHash

    metadata = {}
    if doi:
        metadata["doi"] = doi
    if arxiv_id:
        metadata["arxiv_id"] = arxiv_id

    url = f"https://example.com/{uuid.uuid4()}"
    article = Article(
        url=url,
        url_hash=UrlHash.generate_url_hash(url),
        source="openalex",
        title=title,
        content="content",
        correlation_id=uuid.uuid4(),
        metadata_=metadata,
    )
    db_session.add(article)
    db_session.flush()
    return article


# ---------------------------------------------------------------------------
# ResilientMetricsService: provider fallback chain
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_fetch_all_falls_back_to_next_provider_on_null_result():
    service = ResilientMetricsService([
        MetricHandler(
            metric_key="citation_count", provider_name="semantic_scholar", priority=1,
            extractor=_FakeExtractor(value=None), extractor_spec={},
        ),
        MetricHandler(
            metric_key="citation_count", provider_name="openalex", priority=2,
            extractor=_FakeExtractor(value=42), extractor_spec={},
        ),
    ])

    results = service.fetch_all({"doi": "10.1234/test"})
    assert results == {"citation_count": 42}


@pytest.mark.integration
def test_fetch_all_falls_back_to_next_provider_on_exception():
    service = ResilientMetricsService([
        MetricHandler(
            metric_key="citation_count", provider_name="semantic_scholar", priority=1,
            extractor=_FakeExtractor(raises=True), extractor_spec={},
        ),
        MetricHandler(
            metric_key="citation_count", provider_name="openalex", priority=2,
            extractor=_FakeExtractor(value=7), extractor_spec={},
        ),
    ])

    results = service.fetch_all({"doi": "10.1234/test"})
    assert results == {"citation_count": 7}


@pytest.mark.integration
def test_fetch_all_omits_metric_key_when_all_providers_fail():
    service = ResilientMetricsService([
        MetricHandler(
            metric_key="citation_count", provider_name="semantic_scholar", priority=1,
            extractor=_FakeExtractor(value=None), extractor_spec={},
        ),
        MetricHandler(
            metric_key="citation_count", provider_name="openalex", priority=2,
            extractor=_FakeExtractor(raises=True), extractor_spec={},
        ),
    ])

    results = service.fetch_all({"doi": "10.1234/test"})
    assert results == {}


# ---------------------------------------------------------------------------
# SqlAlchemyArticleMetricsRepository.upsert() against real DB
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_upsert_creates_article_metrics_and_metric_value_rows(db_session):
    from models.article_metrics import ArticleMetrics
    from models.article_metric_value import ArticleMetricValue
    from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository

    article = _make_article(db_session, doi="10.1000/first")
    repo = SqlAlchemyArticleMetricsRepository(session=db_session)

    repo.upsert(article.id, {"citation_count": 15})

    metrics = db_session.query(ArticleMetrics).filter_by(article_id=article.id).first()
    assert metrics is not None
    assert metrics.view_count == 0

    value_row = db_session.query(ArticleMetricValue).filter_by(
        article_id=article.id, metric_key="citation_count",
    ).first()
    assert value_row is not None
    assert int(value_row.value) == 15
    assert value_row.last_flushed_at is not None


@pytest.mark.integration
def test_upsert_updates_existing_metric_value_and_last_flushed_at(db_session):
    from models.article_metric_value import ArticleMetricValue
    from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository

    article = _make_article(db_session, doi="10.1000/second")
    repo = SqlAlchemyArticleMetricsRepository(session=db_session)

    repo.upsert(article.id, {"citation_count": 5})
    first_row = db_session.query(ArticleMetricValue).filter_by(
        article_id=article.id, metric_key="citation_count",
    ).first()
    first_flushed_at = first_row.last_flushed_at

    repo.upsert(article.id, {"citation_count": 9})
    db_session.expire_all()
    second_row = db_session.query(ArticleMetricValue).filter_by(
        article_id=article.id, metric_key="citation_count",
    ).first()

    assert int(second_row.value) == 9
    assert second_row.last_flushed_at >= first_flushed_at
    assert db_session.query(ArticleMetricValue).filter_by(article_id=article.id).count() == 1


@pytest.mark.integration
def test_upsert_does_not_overwrite_existing_view_count(db_session):
    from models.article_metrics import ArticleMetrics
    from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository

    article = _make_article(db_session, doi="10.1000/third")
    db_session.add(ArticleMetrics(article_id=article.id, view_count=100))
    db_session.commit()

    repo = SqlAlchemyArticleMetricsRepository(session=db_session)
    repo.upsert(article.id, {"citation_count": 3})

    db_session.expire_all()
    metrics = db_session.query(ArticleMetrics).filter_by(article_id=article.id).first()
    assert metrics.view_count == 100  # untouched by the metrics-refresh upsert


# ---------------------------------------------------------------------------
# find_stale (SqlAlchemyArticleMetricsRepository)
#
# `core.articles` is a fixed-schema table (016-db-schema-brushup) — no longer
# created fresh per test run, so these use a generously large limit and scope
# assertions by membership (`article.id in {...}`) rather than relying on the
# just-inserted row landing inside a tightly-bounded `LIMIT` window of the
# shared, already-populated real table.
# ---------------------------------------------------------------------------

def _find_stale_ids(db_session, metric_keys=("citation_count",)):
    from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository

    repo = SqlAlchemyArticleMetricsRepository(session=db_session)
    return {row.article_id for row in repo.find_stale(list(metric_keys), limit=10_000)}


@pytest.mark.integration
def test_find_stale_includes_article_with_doi_and_no_metric_value(db_session):
    article = _make_article(db_session, doi="10.2000/no-metrics")

    assert article.id in _find_stale_ids(db_session)


@pytest.mark.integration
def test_find_stale_excludes_article_without_doi_or_arxiv_id(db_session):
    article = _make_article(db_session, title="No identifiers")

    assert article.id not in _find_stale_ids(db_session)


@pytest.mark.integration
def test_find_stale_excludes_article_with_freshly_flushed_metric(db_session):
    from models.article_metric_value import ArticleMetricValue

    article = _make_article(db_session, doi="10.2000/fresh")
    db_session.add(ArticleMetricValue(
        article_id=article.id, metric_key="citation_count", value=10,
        last_flushed_at=datetime.now(timezone.utc),
    ))
    db_session.flush()

    assert article.id not in _find_stale_ids(db_session)


@pytest.mark.integration
def test_find_stale_includes_article_with_metric_value_older_than_one_day(db_session):
    from models.article_metric_value import ArticleMetricValue

    article = _make_article(db_session, doi="10.2000/stale")
    db_session.add(ArticleMetricValue(
        article_id=article.id, metric_key="citation_count", value=10,
        last_flushed_at=datetime.now(timezone.utc) - timedelta(days=2),
    ))
    db_session.flush()

    assert article.id in _find_stale_ids(db_session)
