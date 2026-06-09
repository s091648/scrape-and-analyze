from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.shared.domain.value_objects.tag_mode import TagMode


@dataclass
class Topic:
    """Domain entity representing a topic category for article classification."""
    name: str
    display_name: str
    id: Optional[UUID] = None
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: bool = True
    tag_mode: TagMode = TagMode.UNSUPERVISED
    created_at: Optional[datetime] = None
