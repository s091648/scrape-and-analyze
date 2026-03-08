import requests
from bs4 import BeautifulSoup
from src.scrapers.content_parsers.base_parser import BaseContentParser
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SELECTORS = [
    'article',
    'main',
    '[class*="article-body"]',
    '[class*="article-content"]',
    '[class*="post-content"]',
    '[class*="post-body"]',
    '[class*="entry-content"]',
    '[class*="story-body"]',
    '[class*="content-body"]',
]


class HtmlArticleParser(BaseContentParser):

    def __init__(self, selectors: list[str] | None = None):
        self._selectors = selectors or DEFAULT_SELECTORS

    def parse(self, html: str) -> str:
        """Extract article body from HTML string. Returns '' if no selector matches."""
        soup = BeautifulSoup(html, 'html.parser')
        for selector in self._selectors:
            elem = soup.select_one(selector)
            if elem:
                content = sanitize_content(str(elem))
                if content:
                    return content
        return ''

    def fetch_and_parse(self, url: str, fallback: str = '') -> str:
        """HTTP GET the URL then parse. Returns fallback on any failure."""
        if not url:
            return fallback
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={'User-Agent': 'Digital-Twins-Scraper/1.0'},
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning('html_fetch_failed', url=url, error=str(e))
            return fallback
        result = self.parse(response.text)
        if not result:
            logger.warning('html_no_body_found', url=url)
            return fallback
        return result
