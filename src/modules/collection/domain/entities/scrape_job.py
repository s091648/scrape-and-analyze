from dataclasses import dataclass, field
from typing import Dict, Optional, Union
from uuid import UUID
from .scrape_job_metadata import ScrapeJobMetadata


Metadata = Union[Dict, ScrapeJobMetadata]

@dataclass(frozen=True)
class ScrapeJob:
    """A single unit of scraping work discovered from a source."""
    url: str
    source: str
    source_type: str
    topic_id: Optional[UUID] = None
    prompt_override: Optional[str] = None
    metadata: Optional[Metadata] = field(default_factory=dict)
