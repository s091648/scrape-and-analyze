from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import UUID, uuid4


@dataclass
class ArxivMetadata:
    """ArXiv-specific metadata attached to an article, including authors and paper sections."""
    article_id: UUID
    id: UUID = field(default_factory=uuid4)
    arxiv_id: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    pdf_available: bool = False
    sections: Dict[str, str] = field(default_factory=dict)
