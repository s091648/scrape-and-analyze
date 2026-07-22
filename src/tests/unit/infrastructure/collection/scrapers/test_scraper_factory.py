from unittest.mock import MagicMock
import pytest
from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.value_objects import ArxivKeyword
from shared.selector_config import ArxivConfig, SemanticScholarConfig, OpenAlexConfig


def _make_http_client():
    """Return a minimal mock http_client accepted by ConcreteScraperFactory."""
    mock_http = MagicMock()
    mock_http.with_skip_retry_status.return_value = mock_http
    return mock_http


def test_factory_creates_semantic_scholar_scraper():
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    setting = ScraperSetting(
        source="s2_test",
        source_type="semantic_scholar",
        url="",
        interval_hours=24,
        selector_config=SemanticScholarConfig(max_results=10, days_back=7),
        keyword_items=None,
    )

    factory = ConcreteScraperFactory(http_client=_make_http_client())
    scraper = factory.create_for(setting)

    assert isinstance(scraper, SemanticScholarScraper)


def test_factory_creates_openalex_scraper():
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    setting = ScraperSetting(
        source="oa_test",
        source_type="openalex",
        url="",
        interval_hours=24,
        selector_config=OpenAlexConfig(max_results=20, days_back=7),
        keyword_items=None,
    )

    factory = ConcreteScraperFactory(http_client=_make_http_client())
    scraper = factory.create_for(setting)

    assert isinstance(scraper, OpenAlexScraper)


def test_factory_arxiv_keywords_is_none():
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper

    setting = ScraperSetting(
        source="arxiv_test",
        source_type="arxiv",
        url="",
        interval_hours=24,
        selector_config=ArxivConfig(max_results=30, days_back=7),
        keyword_items=[ArxivKeyword(keyword='ti:"digital twin"')],
    )

    factory = ConcreteScraperFactory(http_client=_make_http_client())
    scraper = factory.create_for(setting)

    assert isinstance(scraper, ArxivScraper)
    # Factory always passes keywords=None for ArXiv (categories come from ArxivCategory items,
    # not ArxivKeyword items — so _keywords is always None for ArXiv scrapers).
    assert scraper._keywords is None


def test_factory_raises_for_unsupported_source_type():
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.modules.collection.domain.exceptions import UnsupportedSourceTypeError

    setting = ScraperSetting(
        source="unknown_test",
        source_type="unknown_source",
        url="",
        interval_hours=24,
        selector_config=None,
        keyword_items=None,
    )

    factory = ConcreteScraperFactory(http_client=_make_http_client())

    with pytest.raises(UnsupportedSourceTypeError):
        factory.create_for(setting)
