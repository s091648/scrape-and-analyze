import requests
import time
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BlogScraper(BaseScraper):
    """Scraper for blog websites with CSS selectors"""

    def __init__(
        self,
        base_url: str,
        source: str,
        selectors: Dict[str, str],
        rate_limit: float = 2.0
    ):
        self.base_url = base_url
        self.source = source
        self.selectors = selectors
        self.rate_limit = rate_limit
        self._robot_parser: Optional[RobotFileParser] = None
        self._robots_loaded: bool = False

    def _get_robot_parser(self) -> RobotFileParser:
        """Get or create robot parser"""
        if self._robot_parser is None:
            self._robot_parser = RobotFileParser()
            parsed = urlparse(self.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                response = requests.get(
                    robots_url,
                    timeout=10,
                    headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
                )
                if response.status_code == 200:
                    self._robot_parser.parse(response.text.splitlines())
                    self._robots_loaded = True
            except Exception as e:
                logger.warning("robots_txt_fetch_failed", url=robots_url, error=str(e))
        return self._robot_parser

    def _can_fetch(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        self._get_robot_parser()
        if not self._robots_loaded:
            return True
        try:
            return self._robot_parser.can_fetch("Digital-Twins-Scraper", url)
        except Exception:
            return True

    def _extract_links(self, html: str) -> List[str]:
        """Extract article links from listing page"""
        soup = BeautifulSoup(html, 'html.parser')
        selector = self.selectors.get('article_link', 'a')
        links = []

        for link in soup.select(selector):
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                links.append(full_url)

        return links

    def _extract_article(self, html: str) -> Tuple[str, str]:
        """Extract title and content from article page"""
        soup = BeautifulSoup(html, 'html.parser')

        title_selector = self.selectors.get('title', 'h1')
        content_selector = self.selectors.get('content', 'article')

        title_elem = soup.select_one(title_selector)
        title = title_elem.get_text(strip=True) if title_elem else ''

        content_elem = soup.select_one(content_selector)
        content = sanitize_content(str(content_elem)) if content_elem else ''

        return title, content

    def _matches_keywords(self, text: str) -> bool:
        """Check if text matches Digital Twins keywords"""
        keywords = ['digital twin', 'digital twins', 'cyber-physical', 'virtual replica']
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def scrape(self) -> List[ScrapedArticle]:
        """Scrape blog for Digital Twins articles"""
        articles = []

        try:
            response = requests.get(
                self.base_url,
                timeout=30,
                headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("blog_listing_fetch_failed", url=self.base_url, error=str(e))
            return []

        links = self._extract_links(response.text)
        logger.info("blog_links_discovered", source=self.source, count=len(links))

        for link in links[:20]:
            if not self._can_fetch(link):
                logger.info("blog_url_blocked_by_robots", url=link)
                continue

            time.sleep(self.rate_limit)

            try:
                article_response = requests.get(
                    link,
                    timeout=30,
                    headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
                )
                article_response.raise_for_status()
            except Exception as e:
                logger.warning("blog_article_fetch_failed", url=link, error=str(e))
                continue

            title, content = self._extract_article(article_response.text)

            if not self._matches_keywords(title) and not self._matches_keywords(content):
                continue

            articles.append(ScrapedArticle(
                url=link,
                title=title,
                content=content,
                published_at=None,
                source=self.source,
            ))

        logger.info("blog_scrape_completed", source=self.source, articles_found=len(articles))
        return articles
