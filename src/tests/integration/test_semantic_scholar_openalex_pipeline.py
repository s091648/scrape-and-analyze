"""Integration tests for the Semantic Scholar / OpenAlex scraper pipeline (spec 011):

  OpenAlexScraper.fetch() / SemanticScholarScraper.fetch()
    -> ScrapedArticle
    -> ArticleScrapedEvent.from_scraped_article()
    -> ProcessScrapedArticleUseCase (real DB)

Verifies that doi/arxiv_id identifiers and the opportunistic citation_count
seed survive all the way into `articles.metadata` and `article_metric_values`
— these are exactly what src/entrypoints/cli/refresh_metrics.py's stale-article
query and WeeklyReportRepoImpl's ranking query depend on (specs 011/014).
Uses a fake API client (no real HTTP calls) with the real dedup/persistence
pipeline, following the pattern in test_process_article.py.
"""
import uuid

import pytest

from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper
from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.application.events import ArticleScrapedEvent


def _job(**metadata_overrides):
    metadata = {
        "work_id": "W123", "paper_id": "SS123",
        "title": "A Great Paper", "abstract": "Abstract text",
        "open_access_pdf_url": None,
        "doi": "10.1234/great-paper",
        "arxiv_id": "2101.00001",
        "citation_count": 55,
        "is_open_access": True,
        "authors": ["Ada Lovelace"],
        "published": None,
        "original_source": "arxiv",
    }
    metadata.update(metadata_overrides)
    return ScrapeJob(
        url=f"https://example.com/paper/{uuid.uuid4()}",
        source="openalex",
        source_type="openalex",
        metadata=metadata,
    )


def _wire_process_use_case(db_session):
    from src.infrastructure.persistence.shared.article_repo_impl import SqlAlchemyArticleRepository
    from src.infrastructure.persistence.collection.article_metrics_repo_impl import SqlAlchemyArticleMetricsRepository
    from src.modules.collection.domain.services import DedupService
    from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase

    article_repo = SqlAlchemyArticleRepository(session=db_session)
    metrics_repo = SqlAlchemyArticleMetricsRepository(session=db_session)
    dedup = DedupService(article_repo=article_repo)
    return ProcessScrapedArticleUseCase(
        article_repo=article_repo,
        dedup_service=dedup,
        article_metrics_repo=metrics_repo,
    )


# ---------------------------------------------------------------------------
# OpenAlex: fetch() -> event -> persisted Article + seeded citation_count
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_openalex_fetch_persists_doi_arxiv_id_and_seeds_citation_count(db_session):
    from models.article import Article
    from models.article_metric_value import ArticleMetricValue

    scraper = OpenAlexScraper(fetch_pdf=False)
    job = _job()

    scraped = scraper.fetch(job)
    event = ArticleScrapedEvent.from_scraped_article(scraped)

    use_case = _wire_process_use_case(db_session)
    outcome, saved = use_case.execute(event)

    from src.modules.collection.application.use_cases import ArticleOutcome
    assert outcome == ArticleOutcome.NEW
    assert saved is not None

    article = db_session.query(Article).filter_by(id=saved.id).first()
    assert article.metadata_["doi"] == "10.1234/great-paper"
    assert article.metadata_["arxiv_id"] == "2101.00001"
    assert article.metadata_["via_source"] == "openalex"

    citation_row = db_session.query(ArticleMetricValue).filter_by(
        article_id=article.id, metric_key="citation_count",
    ).first()
    assert citation_row is not None
    assert int(citation_row.value) == 55


@pytest.mark.integration
def test_openalex_fetch_creates_article_metrics_row_even_without_citation_count(db_session):
    from models.article_metrics import ArticleMetrics

    scraper = OpenAlexScraper(fetch_pdf=False)
    job = _job(citation_count=None)

    scraped = scraper.fetch(job)
    event = ArticleScrapedEvent.from_scraped_article(scraped)

    use_case = _wire_process_use_case(db_session)
    _, saved = use_case.execute(event)

    metrics = db_session.query(ArticleMetrics).filter_by(article_id=saved.id).first()
    assert metrics is not None
    assert metrics.view_count == 0


# ---------------------------------------------------------------------------
# Semantic Scholar: same flow, different scraper
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_semantic_scholar_fetch_persists_doi_and_seeds_citation_count(db_session):
    from models.article import Article
    from models.article_metric_value import ArticleMetricValue

    scraper = SemanticScholarScraper(fetch_pdf=False)
    job = ScrapeJob(
        url=f"https://example.com/paper/{uuid.uuid4()}",
        source="semantic_scholar",
        source_type="semantic_scholar",
        metadata={
            "paper_id": "SS999",
            "title": "Semantic Scholar Paper",
            "abstract": "Abstract",
            "open_access_pdf_url": None,
            "doi": "10.5555/ss-paper",
            "arxiv_id": None,
            "citation_count": 8,
            "is_open_access": False,
            "authors": [],
            "published": None,
            "original_source": "semantic_scholar",
        },
    )

    scraped = scraper.fetch(job)
    event = ArticleScrapedEvent.from_scraped_article(scraped)

    use_case = _wire_process_use_case(db_session)
    outcome, saved = use_case.execute(event)

    from src.modules.collection.application.use_cases import ArticleOutcome
    assert outcome == ArticleOutcome.NEW

    article = db_session.query(Article).filter_by(id=saved.id).first()
    assert article.metadata_["doi"] == "10.5555/ss-paper"
    assert article.metadata_["via_source"] == "semantic_scholar"

    citation_row = db_session.query(ArticleMetricValue).filter_by(
        article_id=article.id, metric_key="citation_count",
    ).first()
    assert citation_row is not None
    assert int(citation_row.value) == 8


# ---------------------------------------------------------------------------
# Dedup: same work re-scraped (e.g. also discovered via arXiv) is skipped
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_duplicate_url_from_second_discover_run_is_not_re_saved(db_session):
    from models.article import Article

    scraper = OpenAlexScraper(fetch_pdf=False)
    job = _job()
    use_case = _wire_process_use_case(db_session)

    scraped_first = scraper.fetch(job)
    event_first = ArticleScrapedEvent.from_scraped_article(scraped_first)
    use_case.execute(event_first)

    # Same URL discovered again (e.g. re-run of the same scraper cycle). The
    # first save has no analysis yet, so dedup reports DUPLICATE_NEEDS_ANALYSIS
    # (not a plain DUPLICATE) and hands back the existing article — either way
    # no second row is inserted.
    scraped_second = scraper.fetch(job)
    event_second = ArticleScrapedEvent.from_scraped_article(scraped_second)
    outcome, existing = use_case.execute(event_second)

    from src.modules.collection.application.use_cases import ArticleOutcome
    assert outcome == ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS
    assert existing is not None
    assert db_session.query(Article).filter_by(url=job.url).count() == 1
