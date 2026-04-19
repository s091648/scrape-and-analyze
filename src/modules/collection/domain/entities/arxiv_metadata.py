from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import UUID


@dataclass
class ArxivMetadata:
    id: UUID = field(default_factory=UUID)
    article_id: UUID
    arxiv_id: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    pdf_available: bool = False
    sections: Dict[str, str] = field(default_factory=dict)
    topic_id: Optional[UUID] = None
