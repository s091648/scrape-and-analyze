from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FetchTask:
    """
    A single unit of fetch work, routable by URL host.

    Adapts the new-architecture (ScrapeJob, BaseScraper) pair into the same
    execute() interface as the old ScrapeTask so queue/executor logic stays
    identical.

    url     — used by QueueRouter to assign the task to a per-host queue.
    source  — human-readable source name for logging.
    job     — domain value object carrying URL + metadata.
    scraper — infrastructure scraper that knows how to fetch this job.
    """
    url: str
    source: str
    job: ScrapeJob
    scraper: Any          # BaseScraper; typed as Any to avoid circular import
    metadata: Dict[str, Any] = field(default_factory=dict)

    def execute(self) -> Optional[ScrapedArticle]:
        try:
            return self.scraper.fetch(self.job)
        except Exception as e:
            logger.error("fetch_task_failed", url=self.url, source=self.source, error=str(e))
            return None