from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.factories import ScraperFactory
from src.modules.collection.domain.value_objects import (
    ArxivConfig,
    ArxivCategory,
    ArxivKeyword,
    BlogConfig,
    OpenAlexConfig,
    OpenAlexKeyword,
    RssConfig,
    RssKeyword,
    SemanticScholarKeyword,
)
from shared.selector_config import SemanticScholarConfig
from .base_scraper import BaseScraper
from .rss_scraper import RssScraper
from .blog_scraper import BlogScraper
from .arxiv_scraper import ArxivScraper
from .openalex_scraper import OpenAlexScraper
from .semantic_scholar_scraper import SemanticScholarScraper
from src.infrastructure.collection.clients import ArxivClient, RssClient

logger = get_logger(__name__)


def _extract(items, vo_type, attr: str) -> list | None:
    """Return a list of `attr` values for keyword_items matching vo_type, or None if empty."""
    if not items:
        return None
    result = [getattr(k, attr) for k in items if isinstance(k, vo_type)]
    return result if result else None


class ConcreteScraperFactory(ScraperFactory):
    """Creates the appropriate BaseScraper for a given ScraperSetting."""

    def __init__(self, http_client=None) -> None:
        if http_client is None:
            from src.infrastructure.shared.http import get_default_client
            http_client = get_default_client()
        self._http_client = http_client

    def create_for(self, setting: ScraperSetting, days_back: int = None) -> BaseScraper:
        cfg = setting.selector_config

        if isinstance(cfg, RssConfig):
            return RssScraper(
                url=setting.url,
                source=setting.source,
                keywords=_extract(setting.keyword_items, RssKeyword, "keyword"),
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
                client=RssClient(http_client=self._http_client),
            )

        if isinstance(cfg, BlogConfig):
            return BlogScraper(
                base_url=setting.url,
                source=setting.source,
                selectors=cfg.selectors,
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
            )

        if isinstance(cfg, ArxivConfig):
            # -1 means no date filter
            effective_days_back = None if days_back == -1 else (days_back if days_back is not None else cfg.days_back)
            # arXiv 429 = IP-level ban; retrying only extends it.
            arxiv_http = self._http_client.with_skip_retry_status(frozenset({429}))
            return ArxivScraper(
                max_results=cfg.max_results,
                days_back=effective_days_back,
                keywords=None,
                categories=_extract(setting.keyword_items, ArxivCategory, "keyword"),
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
                client=ArxivClient(http_client=arxiv_http),
            )

        if isinstance(cfg, SemanticScholarConfig):
            # SS 429 = per-IP daily quota; retrying only burns time.
            ss_http = self._http_client.with_skip_retry_status(frozenset({429}))
            from src.infrastructure.collection.clients import SemanticScholarClient
            return SemanticScholarScraper(
                max_results=cfg.max_results,
                days_back=cfg.days_back if days_back is None else (None if days_back == -1 else days_back),
                keywords=_extract(setting.keyword_items, SemanticScholarKeyword, "keyword"),
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
                client=SemanticScholarClient(http_client=ss_http),
            )

        if isinstance(cfg, OpenAlexConfig):
            # OA 429 = polite pool limit; fail fast and let the next run succeed.
            oa_http = self._http_client.with_skip_retry_status(frozenset({429}))
            from src.infrastructure.collection.clients.openalex_client import OpenAlexClient
            return OpenAlexScraper(
                max_results=cfg.max_results,
                days_back=cfg.days_back if days_back is None else (None if days_back == -1 else days_back),
                keywords=_extract(setting.keyword_items, OpenAlexKeyword, "keyword"),
                topic_id=setting.topic_id,
                prompt_override=setting.prompt_override,
                client=OpenAlexClient(http_client=oa_http),
            )

        logger.warning("unknown_source_type", source_type=setting.source_type)
        raise ValueError(f"Unsupported source_type: {setting.source_type}")
