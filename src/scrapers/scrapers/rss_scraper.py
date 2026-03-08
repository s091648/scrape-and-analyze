import feedparser
import requests
import time
import re
from typing import List
from src.scrapers.scrapers.base_scraper import BaseScraper, ScrapedArticle
from src.scrapers.content_parsers.html_parser import HtmlArticleParser
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

DIGITAL_TWINS_KEYWORDS = [
    r'digital\s+twin',
    r'digital\s+twins',
    r'twin\s+technology',
    r'cyber[\-\s]?physical',
    r'virtual\s+replica',
]


class RssScraper(BaseScraper):
    """Scraper for RSS feeds with Digital Twins keyword filtering"""

    def __init__(self, url: str, source: str, rate_limit: float = 1.0):
        self.url = url
        self.source = source
        self.rate_limit = rate_limit
        self._keyword_pattern = re.compile(
            '|'.join(DIGITAL_TWINS_KEYWORDS),
            re.IGNORECASE
        )
        self._html_parser = HtmlArticleParser()

    def _matches_keywords(self, text: str) -> bool:
        """Check if text matches Digital Twins keywords"""
        if not text:
            return False
        return bool(self._keyword_pattern.search(text))

    def _fetch_full_content(self, url: str, fallback: str) -> str:
        """Fetch full article content from URL, falling back to RSS description."""
        sanitized_fallback = sanitize_content(fallback)
        result = self._html_parser.fetch_and_parse(url, fallback=sanitized_fallback)
        return result

    def scrape(self) -> List[ScrapedArticle]:
        """Scrape RSS feed for Digital Twins articles"""
        try:
            response = requests.get(
                self.url,
                timeout=30,
                headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("rss_fetch_failed", url=self.url, error=str(e))
            return []

        feed = feedparser.parse(response.content)

        if not feed.entries:
            return []

        articles = []

        for entry in feed.entries:
            title = entry.get('title', '')
            description = entry.get('description', '') or entry.get('summary', '')

            # Filter by keywords
            if not self._matches_keywords(title) and not self._matches_keywords(description):
                continue

            content = self._fetch_full_content(entry.get('link', ''), description)

            articles.append(ScrapedArticle(
                url=entry.get('link', ''),
                title=title,
                content=content,
                published_at=entry.get('published', ''),
                source=self.source,
                metadata={'author': entry.get('author')}
            ))

            if self.rate_limit > 0:
                time.sleep(self.rate_limit)

        logger.info("rss_scrape_completed", source=self.source, articles_found=len(articles))
        return articles
