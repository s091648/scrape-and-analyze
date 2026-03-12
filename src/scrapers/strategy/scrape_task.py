from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapeTask:
    """
    A unit of scrape work routable by host.

    url          — used by QueueRouter to determine the target host.
    source       — human-readable source name (e.g. 'arxiv', 'techcrunch').
    _execute_fn  — zero-arg callable injected by the scraper at discover() time.
                   Captures all required state via closure.
    metadata     — optional extra data for logging/debugging.
    """
    url: str
    source: str
    _execute_fn: Callable[[], Optional[ScrapedArticle]] = field(repr=False)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def execute(self) -> Optional[ScrapedArticle]:
        """Invoke the injected fetch function. Returns None on any exception."""
        try:
            return self._execute_fn()
        except Exception as e:
            logger.error("scrape_task_execute_failed", url=self.url, error=str(e))
            return None
