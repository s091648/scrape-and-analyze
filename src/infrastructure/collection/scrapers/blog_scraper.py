from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from uuid import UUID

from bs4 import BeautifulSoup

from src.infrastructure.collection.parsers import HtmlArticleParser
from .base_scraper import BaseScraper
from src.infrastructure.shared.http import get_default_client
from src.shared.logging import get_logger
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle

logger = get_logger(__name__)


class BlogScraper(BaseScraper):
    """Discovers and fetches articles from blog listing pages, respecting robots.txt."""

    def __init__(
        self,
        base_url: str,
        source: str,
        selectors: Dict[str, str],
        topic_id: Optional[UUID] = None,
        prompt_override: Optional[str] = None,
    ) -> None:
        self._base_url = base_url
        self._source = source
        self._selectors = selectors
        self._topic_id = topic_id
        self._prompt_override = prompt_override
        self._robot_parser: Optional[RobotFileParser] = None
        self._robots_loaded: bool = False
        self._html_parser = HtmlArticleParser(
            selectors=[selectors.get("content", "article")]
        )

    def discover(self) -> List[ScrapeJob]:
        """Fetch the blog listing page and extract links to individual articles."""
        try:
            response = get_default_client().get(self._base_url, timeout=30)
        except Exception as e:
            logger.error("blog_listing_fetch_failed", url=self._base_url, error=str(e))
            return []

        links = self._extract_links(response.text)
        jobs = []
        for link in links[:20]:
            if not self._can_fetch(link):
                continue
            jobs.append(ScrapeJob(
                url=link,
                source=self._source,
                source_type="blog",
                topic_id=self._topic_id,
                prompt_override=self._prompt_override,
            ))
        logger.info("blog_discover_complete", source=self._source, count=len(jobs))
        return jobs

    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        """Fetch and parse a single blog article page into a ScrapedArticle."""
        try:
            response = get_default_client().get(job.url, timeout=30)
        except Exception as e:
            logger.warning("blog_article_fetch_failed", url=job.url, error=str(e))
            return None

        title = self._extract_title(response.text)
        content = self._html_parser.parse(response.text)
        if not content:
            return None

        return ScrapedArticle(
            url=job.url,
            title=title,
            content=content,
            source=job.source,
            topic_id=job.topic_id,
            extra={"original_source": job.source},
        )

    def _extract_title(self, html: str) -> str:
        """Extract the article title from HTML using the configured title selector."""
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.select_one(self._selectors.get("title", "h1"))
        return tag.get_text(strip=True) if tag else ""

    def _extract_links(self, html: str) -> List[str]:
        """Extract and deduplicate absolute links from the listing page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        selector = self._selectors.get("links", "a")
        links = []
        for tag in soup.select(selector):
            href = tag.get("href", "")
            full = urljoin(self._base_url, href)
            parsed = urlparse(full)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                links.append(full)
        return list(dict.fromkeys(links))

    def _can_fetch(self, url: str) -> bool:
        """Check robots.txt permission for the given URL; returns True if allowed or unknown."""
        if not self._robots_loaded:
            self._load_robots()
        if self._robot_parser is None:
            return True
        return self._robot_parser.can_fetch("*", url)

    def _load_robots(self):
        """Fetch and parse robots.txt for the base URL host."""
        self._robots_loaded = True
        parsed = urlparse(self._base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            self._robot_parser = RobotFileParser(robots_url)
            self._robot_parser.read()
        except Exception:
            self._robot_parser = None