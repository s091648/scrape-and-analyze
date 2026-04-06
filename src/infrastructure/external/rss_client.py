"""
RssClient — infrastructure adapter for RSS/Atom feed fetching.

Responsibility: HTTP request + feedparser parsing only.
Keyword filtering and article content fetching stay in RssScraper.
"""
import feedparser
from dataclasses import dataclass
from typing import List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RssEntry:
    url: str
    title: str
    description: str
    published: str
    author: Optional[str] = None


class RssClient:
    """
    Thin HTTP + feedparser adapter for RSS/Atom feeds.

    Accepts an HttpClient so rate limiting, retry, and UA rotation
    are handled transparently by the shared infrastructure.
    """

    def __init__(self, http_client=None) -> None:
        if http_client is None:
            from src.infrastructure.http.http_client import get_default_client
            http_client = get_default_client()
        self._http = http_client

    def fetch_feed(self, url: str) -> List[RssEntry]:
        """
        Fetch *url* and return parsed feed entries.

        Returns [] on network or parse failure.
        """
        try:
            response = self._http.get(url, timeout=30)
        except Exception as e:
            logger.error("rss_fetch_failed", url=url, error=str(e))
            return []

        feed = feedparser.parse(response.content)
        if not feed.entries:
            logger.info("rss_feed_empty", url=url)
            return []

        entries = [self._to_entry(e) for e in feed.entries]
        logger.info("rss_entries_fetched", url=url, count=len(entries))
        return entries

    # ── private ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_entry(e) -> RssEntry:
        return RssEntry(
            url=e.get("link", ""),
            title=e.get("title", ""),
            description=e.get("description", "") or e.get("summary", ""),
            published=e.get("published", ""),
            author=e.get("author"),
        )
