import re
from typing import List, Optional

from src.infrastructure.external.rss_client import RssClient, RssEntry
from src.ingestion.models.scraped_article import ScrapedArticle
from src.ingestion.scrapers.base_scraper import BaseScraper
from src.ingestion.parsers.html_parser import HtmlArticleParser
from src.pipeline.task import ScrapeTask
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

DIGITAL_TWINS_KEYWORDS = [
    r"digital\s+twin",
    r"digital\s+twins",
    r"twin\s+technology",
    r"cyber[\-\s]?physical",
    r"virtual\s+replica",
]


class RssScraper(BaseScraper):
    """
    Scraper for RSS feeds.

    Delegates HTTP + feedparser to RssClient (infrastructure).
    Domain decisions here: keyword filtering, article content fetching.
    """

    def __init__(
        self,
        url: str,
        source: str,
        rate_limit: float = 1.0,
        client: RssClient = None,
    ) -> None:
        self.url = url
        self.source = source
        self.rate_limit = rate_limit  # kept for back-compat; delay enforced by worker
        self._client = client or RssClient()
        self._keyword_pattern = re.compile(
            "|".join(DIGITAL_TWINS_KEYWORDS), re.IGNORECASE
        )
        self._html_parser = HtmlArticleParser()

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        entries = self._client.fetch_feed(self.url)
        tasks = []
        for entry in entries:
            if not self._matches_keywords(entry.title) and not self._matches_keywords(
                entry.description
            ):
                continue
            tasks.append(
                ScrapeTask(
                    url=entry.url,
                    source=self.source,
                    _execute_fn=lambda e=entry: self._fetch_article(e),
                )
            )
        logger.info("rss_discover_complete", source=self.source, task_count=len(tasks))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _fetch_article(self, entry: RssEntry) -> Optional[ScrapedArticle]:
        fallback = sanitize_content(entry.description)
        content = self._html_parser.fetch_and_parse(entry.url, fallback=fallback)
        return ScrapedArticle(
            url=entry.url,
            title=entry.title,
            content=content,
            published_at=entry.published,
            source=self.source,
            metadata={"author": entry.author},
        )

    def _matches_keywords(self, text: str) -> bool:
        if not text:
            return False
        return bool(self._keyword_pattern.search(text))
