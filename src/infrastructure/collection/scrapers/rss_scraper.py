import re
from typing import List, Optional
from uuid import UUID

from src.shared.logging import get_logger
from src.infrastructure.collection.clients.rss_client import RssClient
from src.infrastructure.collection.parsers.sanitize_service import SanitizeService
from src.infrastructure.collection.scrapers.base_scraper import BaseScraper
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.infrastructure.collection.parsers import HtmlArticleParser

logger = get_logger(__name__)

_DEFAULT_KEYWORDS = [
    r"digital\s+twin", r"digital\s+twins", r"twin\s+technology",
    r"cyber[\-\s]?physical", r"virtual\s+replica",
]


class RssScraper(BaseScraper):

    def __init__(
        self,
        url: str,
        source: str,
        keywords: Optional[List[str]] = None,
        topic_id: Optional[UUID] = None,
        prompt_override: Optional[str] = None,
        client: RssClient = None,
    ) -> None:
        self._url = url
        self._source = source
        self._topic_id = topic_id
        self._prompt_override = prompt_override
        self._client = client or RssClient()
        patterns = keywords if keywords else _DEFAULT_KEYWORDS
        self._keyword_pattern = re.compile("|".join(patterns), re.IGNORECASE)
        self._html_parser = HtmlArticleParser()

    def discover(self) -> List[ScrapeJob]:
        entries = self._client.fetch_feed(self._url)
        jobs = []
        for entry in entries:
            if not self._matches(entry.title) and not self._matches(entry.description):
                continue
            jobs.append(ScrapeJob(
                url=entry.url,
                source=self._source,
                source_type="rss",
                topic_id=self._topic_id,
                prompt_override=self._prompt_override,
                metadata={
                    "title": entry.title,
                    "description": entry.description,
                    "author": entry.author,
                    "published": entry.published,
                },
            ))
        logger.info("rss_discover_complete", source=self._source, count=len(jobs))
        return jobs

    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        fallback = SanitizeService.sanitize_content(job.metadata.get("description"))
        content = self._html_parser.fetch_and_parse(job.url, fallback=fallback)
        return ScrapedArticle(
            url=job.url,
            title=job.metadata.get("title", ""),
            content=content,
            source=job.source,
            topic_id=job.topic_id,
            published_at=job.metadata.get("published"),
            authors=[job.metadata.get("author")] if job.metadata.get("author") else [],
            extra={"author": job.metadata.get("author")},
        )

    def _matches(self, text: str) -> bool:
        return bool(text and self._keyword_pattern.search(text))