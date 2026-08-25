from abc import abstractmethod
from datetime import datetime
from typing import List, Optional

from dateutil import parser as _dateutil_parser

from src.modules.collection.domain.services import Scraper
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.shared.logging import get_logger

logger = get_logger(__name__)


class BaseScraper(Scraper):
    """
    Infrastructure base for all scrapers.
    Extends the domain Scraper interface with a fetch() method so that
    the same instance can both discover URLs and retrieve article content.
    """

    @abstractmethod
    def discover(self) -> List[ScrapeJob]:
        """Enumerate pending ScrapeJobs for this source."""
        ...

    @abstractmethod
    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        """
        Fetch full article content for *job* and return a ScrapedArticle.
        Returns None on any failure.
        """
        ...

    @staticmethod
    def _parse_published_at(raw) -> Optional[datetime]:
        """Coerce a scraper client's raw published-date value into a real
        datetime for ScrapedArticle.published_at (typed Optional[datetime]).

        024-async-pipeline-refactor: every scraper client hands back a raw
        string here (arXiv/RSS: ISO8601/RFC822 text; OpenAlex/Semantic
        Scholar: a plain "YYYY-MM-DD" string) — under the old sync psycopg2
        driver, Postgres's own text-input parsing silently coerced these on
        INSERT, masking the type mismatch. asyncpg (used by the async
        per-article write path) requires a native datetime for a
        TIMESTAMP WITH TIME ZONE bind parameter and raises DataError on a
        raw string instead. dateutil.parser handles all three formats above.
        """
        if not raw:
            return None
        if isinstance(raw, datetime):
            return raw
        try:
            return _dateutil_parser.parse(raw)
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning("published_at_parse_failed", raw=str(raw), error=str(e))
            return None