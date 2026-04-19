from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class ScrapeJob:
    """A single unit of scraping work discovered from a source."""
    url: str
    source: str
    source_type: str
    topic_id: Optional[UUID] = None
    prompt_override: Optional[str] = None
