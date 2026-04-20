from bs4 import BeautifulSoup
from .base_parser import BaseContentParser
from src.infrastructure.collection.parsers.sanitize_service import SanitizeService
from src.shared.logging import get_logger
from src.infrastructure.shared.http import get_default_client

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
                content = SanitizeService.sanitize_content(str(elem))
                if content:
                    return content
        return ''

    def fetch_and_parse(self, url: str, fallback: str = '') -> str:
        """HTTP GET the URL then parse. Returns fallback on any failure."""
        if not url:
            return fallback
        try:
            response = get_default_client().get(url, timeout=30)
        except Exception as e:
            logger.warning('html_fetch_failed', url=url, error=str(e))
            return fallback
        result = self.parse(response.text)
        if not result:
            logger.warning('html_no_body_found', url=url)
            return fallback
        return result