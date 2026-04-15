from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ScrapedArticle:
    """Data class representing a scraped article."""
    url: str
    title: str
    content: str
    published_at: Optional[str]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    topic_id: Optional[str] = None   # string UUID; converted to UUID in domain layer
    prompt_override: Optional[str] = None
