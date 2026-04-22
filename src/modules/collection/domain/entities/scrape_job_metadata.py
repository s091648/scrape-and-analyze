from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ScrapeJobMetadata:
    """Metadata for a scrape job."""
    arxiv_id: Optional[str] = None
    abstract: Optional[str] = None
    pdf_url: Optional[str] = None
    authors: Optional[list] = field(default_factory=list)
    published: Optional[str] = None
