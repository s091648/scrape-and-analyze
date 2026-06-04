from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

_ARXIV_MAX_ANALYSIS_CHARS = 15_000


@dataclass
class Article:
    url: str
    url_hash: str
    source: str
    title: str
    content: str
    id: UUID = field(default_factory=uuid4)
    published_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    topic_id: Optional[UUID] = None

    def get_analysis_content(self) -> str:
        """Return LLM-ready text based on article source."""
        if self.source in ("arxiv", "semantic_scholar"):
            sections: dict = self.metadata.get("sections") or {}
            if len(sections) >= 2:
                combined = "\n\n".join(
                    f"{name.title()}\n{body}" for name, body in sections.items()
                )
                return combined[:_ARXIV_MAX_ANALYSIS_CHARS]
            return self.metadata.get("abstract", self.content[:2000])
        return self.content
