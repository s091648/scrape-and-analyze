from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class ArxivMetadataEntity:
    article_id: UUID
    id: Optional[UUID] = None
    arxiv_id: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    pdf_available: bool = False
    sections: Dict[str, str] = field(default_factory=dict)
