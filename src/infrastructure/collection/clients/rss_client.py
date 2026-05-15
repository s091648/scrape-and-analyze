"""
RssClient — infrastructure adapter for RSS/Atom feed fetching.

Responsibility: HTTP request + feedparser parsing only.
Keyword filtering and article content fetching stay in RssScraper.
"""
import feedparser
from dataclasses import dataclass
from typing import List, Optional

from src.shared.logging import get_logger

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
            from src.infrastructure.shared.http import get_default_client
            http_client = get_default_client()
        self._http = http_client

    # RSS/Atom readers signal these MIME types — avoids browser content-negotiation
    # that can trigger anti-bot HTML responses instead of XML feed content.
    _RSS_ACCEPT = (
        "application/rss+xml, application/atom+xml, application/xml;q=0.9, "
        "text/xml;q=0.8, */*;q=0.1"
    )

    # RSS clients never send Sec-Fetch-* or sec-ch-ua — strip the browser
    # fingerprint so Cloudflare / Akamai don't return an HTML challenge page
    # instead of XML.  None values are filtered out by requests before sending.
    # Exclude "br" encoding: brotli is not installed, so Brotli-compressed bytes
    # would corrupt the feed content.
    _RSS_HEADERS = {
        "Accept-Encoding": "gzip, deflate",
        "Sec-Fetch-Dest": None,
        "Sec-Fetch-Mode": None,
        "Sec-Fetch-Site": None,
        "Sec-Fetch-User": None,
        "sec-ch-ua": None,
        "sec-ch-ua-mobile": None,
        "sec-ch-ua-platform": None,
        "Upgrade-Insecure-Requests": None,
        "Cache-Control": None,
    }

    def fetch_feed(self, url: str) -> List[RssEntry]:
        """
        Fetch *url* and return parsed feed entries.

        Returns [] on network or parse failure.
        """
        try:
            response = self._http.get(
                url,
                timeout=30,
                headers={"Accept": self._RSS_ACCEPT, **self._RSS_HEADERS},
            )
        except Exception as e:
            logger.error("rss_fetch_failed", url=url, error=str(e))
            return []

        feed = feedparser.parse(response.content)
        if not feed.entries:
            logger.info(
                "rss_feed_empty",
                url=url,
                content_type=response.headers.get("Content-Type", "unknown"),
                bozo=feed.bozo,
                bozo_exception=str(feed.bozo_exception) if feed.bozo else None,
            )
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
