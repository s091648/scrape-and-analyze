import feedparser
import re
from typing import List, Optional

from src.ingestion.models.scraped_article import ScrapedArticle
from src.ingestion.scrapers.base_scraper import BaseScraper
from src.ingestion.parsers.html_parser import HtmlArticleParser
from src.pipeline.task import ScrapeTask
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger
from src.infrastructure.http.http_client import get_default_client

logger = get_logger(__name__)

DIGITAL_TWINS_KEYWORDS = [
    r"digital\s+twin",
    r"digital\s+twins",
    r"twin\s+technology",
    r"cyber[\-\s]?physical",
    r"virtual\s+replica",
]


class RssScraper(BaseScraper):
    """Scraper for RSS feeds with Digital Twins keyword filtering."""

    def __init__(self, url: str, source: str, rate_limit: float = 1.0) -> None:
        self.url = url
        self.source = source
        self.rate_limit = rate_limit  # kept for back-compat; delay enforced by worker
        self._keyword_pattern = re.compile(
            "|".join(DIGITAL_TWINS_KEYWORDS), re.IGNORECASE
        )
        self._html_parser = HtmlArticleParser()

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        """
        Fetch RSS feed, filter entries by keyword, return one ScrapeTask per match.
        Returns [] on fetch or parse failure.
        """
        try:
            response = get_default_client().get(self.url, timeout=30)
        except Exception as e:
            logger.error("rss_fetch_failed", url=self.url, error=str(e))
            return []

        feed = feedparser.parse(response.content)
        if not feed.entries:
            return []

        tasks = []
        for entry in feed.entries:
            title = entry.get("title", "")
            description = entry.get("description", "") or entry.get("summary", "")
            if not self._matches_keywords(title) and not self._matches_keywords(description):
                continue
            tasks.append(ScrapeTask(
                url=entry.get("link", ""),
                source=self.source,
                _execute_fn=lambda e=entry: self._fetch_article(e),
            ))

        logger.info("rss_discover_complete", source=self.source, task_count=len(tasks))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _fetch_article(self, entry) -> Optional[ScrapedArticle]:
        link = entry.get("link", "")
        description = entry.get("description", "") or entry.get("summary", "")
        fallback = sanitize_content(description)
        content = self._html_parser.fetch_and_parse(link, fallback=fallback)
        return ScrapedArticle(
            url=link,
            title=entry.get("title", ""),
            content=content,
            published_at=entry.get("published", ""),
            source=self.source,
            metadata={"author": entry.get("author")},
        )

    def _matches_keywords(self, text: str) -> bool:
        if not text:
            return False
        return bool(self._keyword_pattern.search(text))
