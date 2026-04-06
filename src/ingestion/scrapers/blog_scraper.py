from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

from src.ingestion.models.scraped_article import ScrapedArticle
from src.ingestion.scrapers.base_scraper import BaseScraper
from src.ingestion.parsers.html_parser import HtmlArticleParser
from src.pipeline.task import ScrapeTask
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger
from src.infrastructure.http.http_client import get_default_client

logger = get_logger(__name__)


class BlogScraper(BaseScraper):
    """Scraper for blog websites with CSS selectors."""

    def __init__(self, base_url: str, source: str, selectors: Dict[str, str],
                 rate_limit: float = 2.0) -> None:
        self.base_url = base_url
        self.source = source
        self.selectors = selectors
        self.rate_limit = rate_limit  # kept for back-compat; delay enforced by worker
        self._robot_parser: Optional[RobotFileParser] = None
        self._robots_loaded: bool = False
        self._html_parser = HtmlArticleParser(
            selectors=[selectors.get("content", "article")]
        )

    # ── Public API ────────────────────────────────────────────────────────

    def discover(self) -> List[ScrapeTask]:
        """
        Fetch listing page, extract article links, return one ScrapeTask per link.
        Filters out URLs disallowed by robots.txt.
        """
        try:
            response = get_default_client().get(self.base_url, timeout=30)
        except Exception as e:
            logger.error("blog_listing_fetch_failed", url=self.base_url, error=str(e))
            return []

        links = self._extract_links(response.text)
        logger.info("blog_links_discovered", source=self.source, count=len(links))

        tasks = []
        for link in links[:20]:
            if not self._can_fetch(link):
                logger.info("blog_url_blocked_by_robots", url=link)
                continue
            tasks.append(ScrapeTask(
                url=link,
                source=self.source,
                _execute_fn=lambda u=link: self._fetch_article(u),
            ))
        return tasks

    # ── Private helpers ───────────────────────────────────────────────────

    def _fetch_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            response = get_default_client().get(url, timeout=30)
        except Exception as e:
            logger.warning("blog_article_fetch_failed", url=url, error=str(e))
            return None

        title, content = self._extract_article(response.text)
        if not self._matches_keywords(title) and not self._matches_keywords(content):
            return None

        return ScrapedArticle(
            url=url, title=title, content=content,
            published_at=None, source=self.source,
        )

    def _get_robot_parser(self) -> RobotFileParser:
        if self._robot_parser is None:
            self._robot_parser = RobotFileParser()
            parsed = urlparse(self.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                response = get_default_client().get(robots_url, timeout=10)
                self._robot_parser.parse(response.text.splitlines())
                self._robots_loaded = True
            except Exception as e:
                logger.warning("robots_txt_fetch_failed", url=robots_url, error=str(e))
        return self._robot_parser

    def _can_fetch(self, url: str) -> bool:
        self._get_robot_parser()
        if not self._robots_loaded:
            return True
        try:
            return self._robot_parser.can_fetch("Digital-Twins-Scraper", url)
        except Exception:
            return True

    def _extract_links(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        selector = self.selectors.get("article_link", "a")
        base = self.base_url if self.base_url.endswith("/") else self.base_url + "/"
        return [
            urljoin(base, link.get("href"))
            for link in soup.select(selector)
            if link.get("href")
        ]

    def _extract_article(self, html: str) -> Tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        title_selector = self.selectors.get("title", "h1")
        title_elem = soup.select_one(title_selector)
        title = title_elem.get_text(strip=True) if title_elem else ""
        content = self._html_parser.parse(html)
        return title, content

    def _matches_keywords(self, text: str) -> bool:
        keywords = ["digital twin", "digital twins", "cyber-physical", "virtual replica"]
        return any(kw in text.lower() for kw in keywords)
